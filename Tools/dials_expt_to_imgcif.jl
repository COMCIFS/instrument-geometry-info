# Convert a DIALS .expt file to imgCIF with external links

# Assumptions: single-panel flat detector
# Home position is zero for rotations and translations
# Only reason for new "detector" is different tth or distance
# Only reason for new "goniometer" is different angles

using ArgParse
using JSON
using CrystalInfoFramework
using LinearAlgebra
using Rotations
using Printf
 
load_info(infile) = begin
    ei = JSON.parse(open(infile))
    sanity_check(ei)
    return ei
end

output_imgcif(infile, cmdline_args) = begin
    
    expt_info = load_info(infile)

    output_header()

    gb = get_beam_information(expt_info)
    output_beam_information(gb)

    axis_info = determine_axes(expt_info)
    output_axis_info(axis_info...)

    output_array_info("DETECTOR", length(expt_info["detector"][1]["panels"]), axis_info[end])
    
    scan_info = get_scan_info(expt_info)
    output_scan_axes(scan_info, axis_info[1], axis_info[2])
    output_frame_ids(scan_info)
    output_frame_image(scan_info)

    ext_info = generate_external_locations(scan_info, cmdline_args) 
    output_external_locations(ext_info, scan_info)

end

#=== Radiation ===#

get_beam_information(expt_info) = begin

    wl = expt_info["beam"][]["wavelength"]
    return wl
end

#=== Geometry ===#

determine_axes(expt_info) = begin
    g_axes = determine_gonio_axes(expt_info)
    det_axes = determine_det_axes(expt_info)
    surface_axes = determine_surface_axes(expt_info)
    
    return g_axes, det_axes, surface_axes
end

determine_gonio_axes(js_info) = begin

    # A goniometer in DIALS is a set of fixed axes, one
    # of which rotates. If an axis changes direction, that is a
    # new goniometer.

    g_info = js_info["goniometer"]
    g_f = g_info[1]
 
    axis_dict = Dict()
    if !haskey(g_f, "names")  # single axis then

        @assert length(g_info) == 1
        axis_dict["Omega"] = Dict("axis" => g_f["rotation_axis"])
        
    else
        n_axes = length(g_f["names"])
        for i in 1:n_axes
            ax_vec = g_f["axes"][i]
            ax_vals = map(x -> x["angles"][i], g_info)
            axis_dict[g_f["names"][i]] = Dict("axis" => ax_vec,
                                              "vals" => ax_vals,
                                              "next" => i == n_axes ? "." : "$(g_f["names"][i+1])" 
                                        )
        end
    end
    
    return axis_dict
end

"""
    Determine the axes that move the detector. For axes describing
    pixel positions, see surface_axes
"""
determine_det_axes(js_info) = begin

    # A detector is distinct if
    # its position changes in any way. So a change
    # in distance or 2 theta is a "new" detector.
    # A DIALS detector includes a list of panels
    # arranged in a hierarchy. The two-theta angle
    # is absorbed into the panel centre position.

    # We think a detector is the same if there are
    # the same number of panels, with the same names.

    # For two theta and distance, we find the panel that
    # has a normal parallel to the beam

    d_info = js_info["detector"]
    panels = d_info[1]["panels"]
    pp = find_perp_panel(d_info[1])

    if isnothing(pp)
        throw(error("Unable to find a panel perpendicular to the beam at tth = 0"))
    end

    axis_dict = Dict()

    # two theta for each detector position
    
    axis_info = map(get_two_theta, d_info)

    # Only a non-zero tth will give us the axis direction, otherwise
    # no tth required
    
    poss_axes = filter(x->x[2] != nothing, axis_info)
    tth_axis = nothing

    if length(poss_axes) > 0
        axis_dict["Two_Theta"] = Dict("axis" => first(poss_axes)[2],
                                      "vals" => map(x -> x[1], axis_info),
                                      "next" => ".",
                                      "type" => "rotation"
                                      )
    end
    
    dists = map(x -> get_distance(x["panels"][pp]), d_info)
    axis_dict["Trans"] = Dict("axis" => [0, 0, -1],
                              "vals" => dists,
                              "next" => "Two_Theta",
                              "type" => "translation"
                              )
    return axis_dict
end

"""
    get_two_theta(detector)

Work out the rotation required to make the normal to
the module parallel to the beam. This assumes that
the panel provided is perpendicular to the beam at
tth = 0. `detector` is a single "detector" entry.
"""
get_two_theta(detector) = begin

    pp = find_perp_panel(detector)

    panel = detector["panels"][pp]
    normal = LinearAlgebra.normalize(cross(panel["fast_axis"], panel["slow_axis"]))

    @debug "Normal to surface" normal
    if norm(normal - [0,0,1]) < 0.0001
        return 0.0, nothing
    end

    if normal[3] > 0 #pointing towards sample 
        normal = normal * -1.0
    end

    rb = rotation_between([0,0,-1],normal)
    tth = rad2deg(rotation_angle(rb))
    axis = rotation_axis(rb)

    return tth, axis
end

get_distance(panel) = begin

    # The distance is the projection of a pixel vector onto the normal
    # to the panel

    normal = LinearAlgebra.normalize(cross(panel["fast_axis"], panel["slow_axis"]))
    return abs(dot(panel["origin"], normal))
end

"""
    Find a panel that is perpendicular to the beam at tth=0. This will just
    be the first panel for which a rotation about [1,0,0] can bring it
    perpendicular.
"""
find_perp_panel(d_info) = begin

    # Find a panel with normal having x component 0

    for (i,p) in enumerate(d_info["panels"])
        normal = LinearAlgebra.normalize(cross(p["fast_axis"], p["slow_axis"]))

        if isapprox(normal[1], 0.0, atol = 0.0001) #can be rotated about X to zero
            return i
        end
    end
    return nothing
end

"""
   Return the axis directions of each panel when tth = 0
"""
determine_surface_axes(js_info) = begin
    
    d_info = js_info["detector"][1]

    axis_dict = Dict()
    
    tth, axis = get_two_theta(d_info)
    for (i, panel) in enumerate(d_info["panels"])
        fast = panel["fast_axis"]
        slow = panel["slow_axis"]
        origin = panel["origin"]
        
        if !isnothing(axis)
            unrotator = Rotations.AngleAxis(-1*deg2rad(tth), axis...)
            fast = unrotator * fast
            slow = unrotator * slow
            origin = unrotator * origin
        end

        origin = [origin[1], origin[2], 0.0]    #z component is distance
        
        axis_dict["ele$(i)_x"] = Dict("axis" => fast,
                                    "next" => "Trans",
                                      "origin" => origin,
                                      "pix_size" => panel["pixel_size"][1],
                                      "num_pix" => panel["image_size"][1],
                                      "prec" => 1,
                                      "element" => i
                                    )
        axis_dict["ele$(i)_y"] = Dict("axis" => slow,
                                    "next" => "ele$(i)_x",
                                      "origin" => [0.0, 0.0, 0.0],
                                      "pix_size" => panel["pixel_size"][2],
                                      "num_pix" => panel["image_size"][2],
                                      "prec" => 2,
                                      "element" => i
                                    )
    end
    return axis_dict
end

# === Scan information === #

"""
    An "experiment" in the .expt file is roughly the equivalent of a
    "scan" in imgCIF, as long as "beam" and "detector" in "experiment"
    remain the same.

    TODO: determine if stated axis directions change with angle.

    `g_axes` and `d_axes` contain information about axis settings
    for each scan, with the order of appearance corresponding to
    the order they appear in `goniometer` or `detector`
"""
get_scan_info(expt_info) = begin

    scan_list = []
    for (scan_no, one_expt) in enumerate(expt_info["experiment"])

        scanid = "SCAN0$scan_no"

        scan_info = Dict()

        gonio = expt_info["goniometer"][one_expt["goniometer"] + 1]
        scan_axis = gonio["names"][gonio["scan_axis"] + 1]

        # get scan information

        scan_block = expt_info["scan"][one_expt["scan"] + 1]
        start = scan_block["oscillation"][1]
        step = scan_block["oscillation"][2]
        num_frames = length(scan_block["exposure_time"])
        full_range = step * num_frames #to end of final step

        # Store

        scan_info["scan_axis"] = scan_axis
        scan_info["start"] = start
        scan_info["step"] = step
        scan_info["range"] = full_range
        scan_info["gonio_idx"] = one_expt["goniometer"] + 1
        scan_info["det_idx"] = one_expt["detector"] + 1
        scan_info["num_frames"] = num_frames
        scan_info["integration_time"] = scan_block["exposure_time"]
        scan_info["images"] = expt_info["imageset"][one_expt["imageset"]+ 1]["template"]

        push!(scan_list, scan_info)
    end
    
    return scan_list 
end

"""
   Based on command-line arguments and our knowledge of the scans, we
   create per-scan output information.
"""
generate_external_locations(scan_list, cmdline_config) = begin

    ext_info = []
    for (scan_no, one_expt) in enumerate(scan_list)
        local_name = one_expt["images"]
        name_dict = Dict()
        name_dict["tail"] = find_filename(local_name, cmdline_config["cut"][])

        if !haskey(cmdline_config, "scans")
            if haskey(cmdline_config, "location")
                name_dict["archive"] = cmdline_config["location"][]
            else
                name_dict["archive"] = nothing
                name_dict["tail"] = local_name
            end
        else
            name_dict["archive"] = cmdline_config["scans"][scan_no]
        end

        if cmdline_config["format"] == []
            image_type = determine_file_type(name_dict["tail"])
        else
            image_type = cmdline_config["format"][]
        end

        if !isnothing(name_dict["archive"])
            if cmdline_config["archive-type"] == []
                arch_type = determine_arch_type(name_dict["archive"])
            else
                arch_type = cmdline_config["archive-type"][]
            end

            name_dict["arch_type"] = arch_type
        end

        name_dict["image_type"] = image_type
        
        push!(ext_info, name_dict)
    end

    return ext_info
end

find_filename(full_name, cutspec) = begin
    a = match(Regex("(" * cutspec * ")"), full_name)
    if isnothing(a)
        @warn "Couldn't find $cutspec in $full_name"
    else
        tl_st = a.offsets[1] + length(cutspec)
        return full_name[tl_st:end]
    end

    return full_name
end

determine_arch_type(arch_name) = begin
    comps = split(arch_name, ".")
    if comps[end] == "tgz" || comps[end] == "gz" && comps[end-1] == "tar"
        return "TGZ"
    end
    
    if comps[end] == "tbz" || comps[end] == "bz2" && comps[end-1] == "tar"
        return "TBZ"
    end

    if comps[end] == "zip"
        return "ZIP"
    end

    if comps[end] == "txz" || comps[end] == "xz" && comps[end-1] == "tar"
        return "TXZ"
    end

end

determine_file_type(file_name) = begin
    
    comps = split(file_name,".")
    if comps[end] == "cbf"
        return "CBF"
    else
        @error "Unable to determine type of image file"
    end
    
end

# ============ Output =============#

output_header() = begin
    println("""#\\#CIF_2.0
# CIF converted from DIALS .expt file
# Conversion routine version 0.1
data_exptinfo
""")
end

output_beam_information(wl) = begin
    println("_diffrn_radiation_wavelength.id    1")
    println("_diffrn_radiation_wavelength.value $wl")
    println("_diffrn_radiation.type             xray")
    println()
end

output_axis_info(g_axes, d_axes, s_axes) = begin
    header = """loop_
_axis.id
_axis.depends_on
_axis.equipment
_axis.type
_axis.vector[1]
_axis.vector[2]
_axis.vector[3]
_axis.offset[1]
_axis.offset[2]
_axis.offset[3]
"""
    println(header)

    # round values

    tth = map(x -> round(x, digits = 6), d_axes["Two_Theta"]["axis"])

    for (k,v) in g_axes
        @debug "Output axis now $k"
        print("$k   $(v["next"])   goniometer  rotation   $(v["axis"][1]) $(v["axis"][2]) $(v["axis"][3])")
        println("   0.0 0.0 0.0")
    end

    for (k,v) in d_axes
        @debug "Output axis now $k"
        print("$k   $(v["next"])   detector  $(v["type"])   $(v["axis"][1]) $(v["axis"][2]) $(v["axis"][3])")
        println("   0.0 0.0 0.0")
    end

    for (k,v) in s_axes
        @debug "Output surface axis $k"
        print("$k   $(v["next"])   detector  translation  $(v["axis"][1]) $(v["axis"][2]) $(v["axis"][3])")
        println("   $(v["origin"][1]) $(v["origin"][2]) $(v["origin"][3]) ")

    end

    println()
end

"""
    Output information about the layout of the pixels. We assume two
    axes, with the first one the fast direction, and that there is no
    dead space between pixels.
"""
output_array_info(det_name, num_els, s_axes) = begin

    # Output info about elements
    println("""
        _diffrn_detector.id $det_name
        _diffrn_detector.diffrn_id DIFFRN
        """)
    
    println("""loop_
        _diffrn_detector_element.id
        _diffrn_detector_element.detector_id
        """)
        
    for one_el in 1:num_els
        println("ELEMENT$one_el    $det_name")
    end

    println()
    
    println("""
    loop_
    _diffrn_detector_axis.detector_id
    _diffrn_detector_axis.axis_id
     DETECTOR Two_Theta
     DETECTOR Trans
    """)

    println()
    
    println("""
        loop_
          _array_structure_list_axis.axis_id
          _array_structure_list_axis.axis_set_id
          _array_structure_list_axis.displacement
          _array_structure_list_axis.displacement_increment
    """)

    set_no = 1
    for (axis, v) in s_axes
        println("$axis    $set_no      $(v["pix_size"]/2)    $(v["pix_size"])")
        set_no += 1
    end

    println()
    
    println("""
    loop_
      _array_structure_list.array_id
      _array_structure_list.axis_set_id
      _array_structure_list.direction
      _array_structure_list.index
      _array_structure_list.precedence
      _array_structure_list.dimension
    """)

    set_no = 1
    for (axis, v) in s_axes
        println("1            $set_no          increasing              $(v["prec"]) $(v["prec"]) $(v["num_pix"])")
        set_no += 1
    end

    println()
end

"""
    The scan axis information is available in the expt_info
"""
output_scan_axes(scan_list, g_axes, d_axes) = begin
    println("""
  loop_
    _diffrn_scan_axis.scan_id
    _diffrn_scan_axis.axis_id
    _diffrn_scan_axis.displacement_start
    _diffrn_scan_axis.displacement_increment
    _diffrn_scan_axis.displacement_range
    _diffrn_scan_axis.angle_start
    _diffrn_scan_axis.angle_increment
    _diffrn_scan_axis.angle_range
    """)

    for (scan_no, one_scan) in enumerate(scan_list)

        scanid = "SCAN0$scan_no"
        
        # get axis setting information
        
        gi = one_scan["gonio_idx"]
        di = one_scan["det_idx"]
        
        for (ax, v) in g_axes
            if ax == one_scan["scan_axis"]
                println("$scanid  $ax  . . . $(one_scan["start"]) $(one_scan["step"]) $(one_scan["range"])")
            else
                println("$scanid  $ax  . . . $(v["vals"][gi]) 0 0")
            end
        end

        for (ax, v) in d_axes
            if ax == "Trans"
                println("$scanid $ax $(v["vals"][di]) 0.0 0.0 . . .")
            else
                println("$scanid $ax . . . $(v["vals"][di]) 0.0 0.0")
            end
        end

        println()
    end

end

output_frame_ids(scan_list) = begin

    println("""
    loop_
    _diffrn_scan.id 
    _diffrn_scan.frame_id_start
    _diffrn_scan.frame_id_end
    _diffrn_scan.frames
    """)

    counter = 1
    for (scan_no, one_scan) in enumerate(scan_list)
        end_cnt = counter + one_scan["num_frames"] - 1
        println("SCAN0$scan_no frm$counter  frm$end_cnt $(one_scan["num_frames"])")
        counter = end_cnt + 1
    end

    # Assign frames to scans
    println("""
        loop_
    _diffrn_scan_frame.frame_id
    _diffrn_scan_frame.scan_id
    _diffrn_scan_frame.frame_number
    _diffrn_scan_frame.integration_time
    """)

    counter = 1
    for (scan_no, one_scan) in enumerate(scan_list)
        for one_frame in 1:one_scan["num_frames"]
            exp_time = one_scan["integration_time"]
            println("frm$counter    SCAN0$scan_no  $one_frame $(exp_time[one_frame])")
            counter += 1
        end
    end

    println()
end

"""
   Link frames to binary images

    TODO: Match array and element names
"""
output_frame_image(scan_info) = begin
    println("""loop_
    _diffrn_data_frame.id
    _diffrn_data_frame.detector_element_id
    _diffrn_data_frame.array_id
    _diffrn_data_frame.binary_id
    """)

    counter = 1
    for one_scan in scan_info
        for i in 1:one_scan["num_frames"]
            println("frm$counter    ELEMENT    IMAGE    $counter")
            counter += 1
        end
    end

    println()
    
    # Now link images with external locations

    println("""
        loop_
    _array_data.array_id
    _array_data.binary_id
    _array_data.external_data_id
    """)

    for i in 1:counter-1
        println("IMAGE    $i  $i")
    end

end

"""
   External locations must be of uniform type, and are organised in scan order.
"""
output_external_locations(ext_info, scan_list) = begin
    println("""
    loop_
        _array_data_external_data.id
        _array_data_external_data.format
        _array_data_external_data.uri""")
    if haskey(ext_info[1],"arch_type")
        println("     _array_data_external_data.archive_format")
        println("     _array_data_external_data.archive_path")
    end

    counter = 1
    for (scan_no, one_ext) in enumerate(ext_info)
        for one_file in 1:scan_list[scan_no]["num_frames"]
            print("$counter   $(one_ext["image_type"]) ")
            location = encode_scan_step(one_ext["tail"], one_file)
            if !haskey(one_ext, "arch_type") 
                println("$location")
            else
                println("$(one_ext["archive"])  $(one_ext["arch_type"])  $location")
            end
            counter += 1
        end
    end
    
end

"""
    Encode the file number into a scan template. The template has a sequence of
    `#` characters for encoding the integer value of the step number.
"""
encode_scan_step(template, val) = begin
    m = match(r"(#+)\.", template)
    if isnothing(m) return template end   #cannot change
    
    num_hashes = length(m.captures[1])
    printspec = replace(template, '#'^num_hashes => "%0$(num_hashes)i")
    Printf.format(Printf.Format(printspec), val)
end


#=== Sanity check ===#

"""
    Check for all the things that we assume
"""
sanity_check(js_info) = begin

    # Detector checks
    
    d_info = js_info["detector"]

    pc = map(x -> length(x["panels"]), d_info)

    if length(unique!(pc)) != 1
        throw(error("More than one detector, cannot convert"))
    end

    # Assume if names are the same, is the same panel
    
    for i in 1:pc[]
        pnames = map(x -> x["panels"][i]["name"], d_info)
        if length(unique!(pnames)) != 1
            throw(error("Panel $i is not uniformly named ($pnames)"))
        end
    end

    
end

#=== Command line ===#

parse_cmdline(d) = begin

    s = ArgParseSettings(d)

    @add_arg_table! s begin
        "-s", "--scans"
        nargs = '+'
        help = "Full URL of archive for each scan, in order"
        metavar = "url"
        
        "-l", "--location"
        help = "URL of archive containing all images (use -s for multiple archives)"
        nargs = 1
        metavar = "url"

        "-c", "--cut"
        nargs = 1
        metavar = "match"
        help = "All characters in local file name following <match> refer to location within archive"

        "-f", "--format"
        nargs = 1
        help = "Format of image files, should be one listed in imgCIF dictionary"

        "-z", "--archive-type"
        nargs = 1
        help = "Type of overall archive, should be of type listed in imgCIF dictionary"

        "expt_file"
        help = "DIALS .expt file for conversion"
        required = true
    end

    parse_args(s)

end

if abspath(PROGRAM_FILE) == @__FILE__

    # Process arguments

    banner = """Convert DIALS expt file to imgCIF

The command-line arguments are used to indicate the relationship
between files in local directories processed by DIALS and files
in permanent archives. If the -s option is used, information
for all scans must be provided and -l is ignored.
"""
    parsed_args = parse_cmdline(banner)
    infile = parsed_args["expt_file"]

    @debug parsed_args

    output_imgcif(infile, parsed_args)
end
