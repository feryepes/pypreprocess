import os
import pylab as pl
from nipy.labs import viz
import nibabel
import numpy as np
import nipy.labs.statistical_mapping as sm
from nipy.modalities.fmri.design_matrix import DesignMatrix
from base_reporter import *
import shutil
import inspect


def generate_level1_stats_table(zmap, mask,
                           output_html_path,
                           title=None,
                           threshold=0.001,
                           method='fpr', cluster_th=0, null_zmax='bonferroni',
                           null_smax=None, null_s=None, nmaxima=4,
                           cluster_pval=.05):
    """
    Parameters
    ----------
    zmap: image object
        z-map data image
    mask: image object or string
        brain mask defining ROI
    output_html_path, string,
                      path where the output html should be written
    threshold, float, optional
               (p-variate) frequentist threshold of the activation image
    method, string, optional
            to be chosen as height_control in
            nipy.labs.statistical_mapping
    cluster_th, scalar, optional,
             cluster size threshold
    null_zmax: optional,
               parameter for cluster level statistics (?)
    null_s: optional,
             parameter for cluster level statistics (?)
    nmaxima: optional,
             number of local maxima reported per supra-threshold cluster
    """

    # sanity
    if isinstance(zmap, basestring):
        zmap = nibabel.load(zmap)
    if isinstance(mask, basestring):
        mask = nibabel.load(mask)

    # Compute cluster statistics
    nulls = {'zmax': null_zmax, 'smax': null_smax, 's': null_s}

    """
    if null_smax is not None:
        print "a"
        clusters, info = sm.cluster_stats(zmap, mask, height_th=threshold,
                                          nulls=nulls)
        clusters = [c for c in clusters if c['cluster_pvalue']<cluster_pval]
    else:
        print "b"
        clusters, info = sm.cluster_stats(zmap, mask, height_th=threshold,
                                          height_control=method.lower(),
                                          cluster_th=cluster_th, nulls=nulls)

    """

    # do some sanity checks
    if title is None:
        title = "Level 1 Statistics"

    if cluster_th > 0:
        title += " (clusters with < %i voxels not shown)" % cluster_th

    clusters, info = sm.cluster_stats(zmap, mask, height_th=threshold,
                                      nulls=nulls, cluster_th=cluster_th,)
    if clusters is not None:
        clusters = [c for c in clusters if c['cluster_pvalue'] < cluster_pval]

    #if clusters == None or info == None:
    #    print "No results were written for %s" % zmap_file_path
    #    return
    if clusters == None:
        clusters = []

    # Make HTML page
    page = open(output_html_path, mode="w")
    page.write("<center>\n")
    page.write("<b>%s</b>\n" % title)
    page.write("<table border = 1>\n")
    page.write("<tr><th colspan=4> Voxel significance </th>\
    <th colspan=3> Coordinates in MNI referential</th>\
    <th>Cluster Size</th></tr>\n")
    page.write("<tr><th>p FWE corr<br>(Bonferroni)</th>\
    <th>p FDR corr</th><th>Z</th><th>p uncorr</th>")
    page.write("<th> x (mm) </th><th> y (mm) </th><th> z (mm) </th>\
    <th>(voxels)</th></tr>\n")

    for cluster in clusters:
        maxima = cluster['maxima']
        size = cluster['size']
        for j in range(min(len(maxima), nmaxima)):
            temp = ["%.3f" % cluster['fwer_pvalue'][j]]
            temp.append("%.3f" % cluster['fdr_pvalue'][j])
            temp.append("%.2f" % cluster['zscore'][j])
            temp.append("%.3f" % cluster['pvalue'][j])
            for it in range(3):
                temp.append("%.0f" % maxima[j][it])
            if j == 0:
                # Main local maximum
                temp.append('%i' % size)
                page.write('<tr><th align="center">' + '</th>\
                <th align="center">'.join(temp) + '</th></tr>')
            else:
                # Secondary local maxima
                page.write('<tr><td align="center">' + '</td>\
                <td align="center">'.join(temp) + '</td><td></td></tr>\n')

    nclust = len(clusters)
    nvox = sum([clusters[k]['size'] for k in range(nclust)])

    page.write("</table>\n")
    page.write("Number of voxels: %i<br>\n" % nvox)
    page.write("Number of clusters: %i<br>\n" % nclust)

    if info is not None:
        page.write("Threshold Z = %.2f (%s control at %.3f)<br>\n" \
                     % (info['threshold_z'], method, threshold))
        page.write("Cluster size threshold p<%s" % cluster_pval)
    else:
        page.write("Cluster size threshold = %i voxels" % cluster_th)

    page.write("</center>\n")
    page.close()


def generate_subject_stats_report(
    stats_report_filename,
    contrasts,
    z_maps,
    mask,
    design_matrix=None,
    subject_id=None,
    anat=None,
    anat_affine=None,
    threshold=2.3,
    cluster_th=0,
    cmap=viz.cm.cold_hot,
    start_time=None,
    progress_logger=None,
    shutdown_all_reloaders=True,
    **glm_kwargs
    ):
    """Generates a report summarizing the statistical methods and results

    Parameters
    ----------
    stats_report_filename: string:
        html file to which output (generated html) will be written

    contrasts: dict of arrays
        contrasts we are interested in; same number of contrasts as zmaps;
        same keys

    zmaps: dict of image objects or strings (image filenames)
        zmaps for contrasts we are interested in; one per contrast id

    mask: 'nifti image object'
        brain mask for ROI

    design_matrix: 'DesignMatrix' or np.lib.io.Npz containing such, or list
    of these
        design matrix(ces) for the experimental conditions

    contrasts: dict of arrays
       dictionary of contrasts of interest; the keys are the contrast ids,
       the values are contrast values (lists)

    z_maps: dict of 3D image objects or strings (image filenames)
       dict with same keys as 'contrasts'; the values are paths of z-maps
       for the respective contrasts

    anat: 3D array (optional)
        brain image to serve bg unto which activation maps will be plotted;
        passed to viz.plot_map API

    anat_affine: 2D array (optional)
        affine data for the anat

    threshold: float (optional)
        threshold to be applied to activation maps voxel-wise

    cluster_th: int (optional)
        minimal voxel count for clusteres declared as 'activated'

    cmap: cmap object (default viz.cm.cold_hot)
        color-map to use in plotting activation maps

    start_time: string (optiona)
        start time for the stats analysis (useful for the generated
        report page)

    progress_logger: ProgressLogger object (optional)
        handle for logging progress

    shutdown_all_reloaders: bool (optional, default True)
        if True, all pages connected to the stats report page will
        be prevented from reloading after the stats report page
        has been completely generated

    **glm_kwargs:
        kwargs used to specify the control parameters used to specify the
        experimental paradigm and the GLM

    """

    # prepare for stats reporting
    if progress_logger is None:
        progress_logger = ProgressReport()

    output_dir = os.path.dirname(stats_report_filename)

    # copy css and js stuff to output dir
    shutil.copy(os.path.join(ROOT_DIR, "js/jquery.min.js"), output_dir)
    shutil.copy(os.path.join(ROOT_DIR, "js/base.js"), output_dir)
    shutil.copy(os.path.join(ROOT_DIR, "css/fsl.css"), output_dir)

    # initialize gallery of design matrices
    design_thumbs = ResultsGallery(
        loader_filename=os.path.join(output_dir,
                                     "design.html")
        )

    # initialize gallery of activation maps
    activation_thumbs = ResultsGallery(
        loader_filename=os.path.join(output_dir,
                                     "activation.html")
        )

    # get caller module handle from stack-frame
    frm = inspect.stack()[1]
    caller_module = inspect.getmodule(frm[0])
    caller_script_name = caller_module.__file__
    caller_source_code = get_module_source_code(caller_script_name)

    methods = """
    GLM and Statistical Inference have been done using the <i>%s</i> script, \
powered by <a href="%s">nipy</a>. Statistic images have been thresholded at \
Z>%s voxel-level.
    """ % (caller_script_name, NIPY_URL, threshold)

    # report the control parameters used in the paradigm and analysis
    design_params = ""
    if len(glm_kwargs):
        design_params += ("The following control parameters were used for  "
                    " specifying the experimental paradigm and fitting the "
                    "GLM:<br/><ul>")

        design_params += dict_to_html_ul(glm_kwargs)

    if start_time is None:
        start_time = time.ctime()

    report_title = "GLM and Statistical Inference"
    if not subject_id is None:
        report_title += " for subject %s" % subject_id

    level1_html_markup = get_subject_report_stats_html_template(
        ).substitute(
        title=report_title,
        start_time=start_time,
        subject_id=subject_id,

        # insert source code stub
        source_script_name=caller_script_name,
        source_code=caller_source_code,

        design_params=design_params,
        methods=methods,
        cmap=cmap.name)

    with open(stats_report_filename, 'w') as fd:
        fd.write(str(level1_html_markup))
        fd.close()

    progress_logger.log("<b>Level 1 statistics</b><br/><br/>")

    # create design matrix thumbs
    design_matrices = design_matrix
    if not design_matrices is None:
        if not isinstance(design_matrices, list):
            design_matrices = [design_matrices]

        for design_matrix, j in zip(design_matrices,
                                    xrange(len(design_matrices))):
            if not isinstance(design_matrix, DesignMatrix):
                if design_matrix.endswith('.npz'):
                    npz = np.load(design_matrix)
                    design_matrix = DesignMatrix(npz['X'],
                                                 npz['conditions'],
                                                 )
                else:
                    # XXX handle other dmat formats like ndarrays, etc.
                    raise TypeError(("Design matric format unknown; "
                                     "must be DesignMatrix object or"
                                     " .npz file containing such object"),
                                    )

            ax = design_matrix.show()
            ax.set_position([.05, .25, .9, .65])
            dmat_outfile = os.path.join(output_dir,
                                        'design_matrix_%i.png' % (j + 1),
                                        )
            pl.savefig(dmat_outfile, bbox_inches="tight", dpi=200)

            thumb = Thumbnail()
            thumb.a = a(href=os.path.basename(dmat_outfile))
            thumb.img = img(src=os.path.basename(dmat_outfile),
                                     height="500px",
                                     )
            thumb.description = "Design Matrix"
            thumb.description += " %s" % (j + 1) if len(
                design_matrices) > 1 else ""

            # commit activation thumbnail into gallery
            design_thumbs.commit_thumbnails(thumb)

    # make colorbar (place-holder, will be overridden, once we've figured out
    # the correct end points) for activations
    colorbar_outfile = os.path.join(output_dir,
                                    'activation_colorbar.png')
    make_standalone_colorbar(cmap, threshold, 8., colorbar_outfile)

    # create activation thumbs
    _vmax = 0
    _vmin = threshold
    for j in xrange(len(contrasts)):
        contrast_id = contrasts.keys()[j]
        contrast_val = contrasts[contrast_id]
        z_map = z_maps[contrast_id]

        # compute cut_coords for viz.plot_map(..) API
        # XXX review computation of cut_coords, vmin, and vmax; not clean!!!
        if isinstance(z_map, basestring):
            z_map = nibabel.load(z_map)
        pos_data = z_map.get_data() * (np.abs(z_map.get_data()) > 0)
        n_axials = 12
        delta_z_axis = 3
        z_axis_max = np.unravel_index(
            pos_data.argmax(), z_map.shape)[2]
        z_axis_min = np.unravel_index(
            np.argmax(-pos_data), z_map.shape)[2]
        z_axis_min, z_axis_max = (min(z_axis_min, z_axis_max),
                                  max(z_axis_max, z_axis_min))
        z_axis_min = min(z_axis_min, z_axis_max - delta_z_axis * n_axials)
        cut_coords = np.linspace(z_axis_min, z_axis_max, n_axials)

        # compute vmin and vmax
        vmax = pos_data.max()
        vmin = -vmax

        # vmax = max(- z_map.get_data().min(), z_map.get_data().max())
        # vmin = - vmax

        # # update colorbar endpoints
        _vmax = max(_vmax, vmax)

        # plot activation proper
        viz.plot_map(pos_data, z_map.get_affine(),
                     cmap=cmap,
                     anat=anat,
                     anat_affine=anat_affine,
                     vmin=vmin,
                     vmax=vmax,
                     threshold=threshold,
                     slicer='z',
                     cut_coords=cut_coords,

                     black_bg=True,
                     )

        # store activation plot
        z_map_plot = os.path.join(output_dir,
                                  "%s_z_map.png" % contrast_id)
        pl.savefig(z_map_plot, dpi=200, bbox_inches='tight',
                   facecolor="k",
                   edgecolor="k")
        stats_table = os.path.join(output_dir,
                                   "%s_stats_table.html" % contrast_id)

        # create thumbnail for activation
        thumbnail = Thumbnail()
        thumbnail.a = a(href=os.path.basename(stats_table))
        thumbnail.img = img(
            src=os.path.basename(z_map_plot), height="200px",)
        thumbnail.description = "%s contrast: %s" % (contrast_id, contrast_val)
        activation_thumbs.commit_thumbnails(thumbnail)

        # generate level 1 stats table
        title = "Level 1 stats for %s contrast" % contrast_id
        generate_level1_stats_table(
            z_map, mask,
            stats_table,
            title=title,
            cluster_th=cluster_th,
            )

    # make colorbar for activations
    make_standalone_colorbar(
        cmap, _vmin, _vmax, colorbar_outfile)

    # we're done, shut down re-loaders
    progress_logger.log('<hr/>')

    # prevent stats report page from reloading henceforth
    progress_logger.finish(stats_report_filename)

    # prevent any related page from reloading
    if shutdown_all_reloaders:
        progress_logger.finish_dir(output_dir)

    # return generated html
    with open(stats_report_filename, 'r') as fd:
        stats_report = fd.read()
        fd.close()

        return stats_report
