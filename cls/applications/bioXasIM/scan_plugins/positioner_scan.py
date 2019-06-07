'''
Created on Aug 25, 2014

@author: bergr
'''
'''
Created on Aug 25, 2014

@author: bergr
'''
from PyQt5 import uic
import os
from cls.applications.bioXasIM.bl07ID01 import MAIN_OBJ, DEFAULTS
from cls.applications.bioXasIM.device_names import *
#from cls.applications.pyStxm.scan_plugins.base import ScanParamWidget, zp_focus_modes
from cls.scanning.base import ScanParamWidget, zp_focus_modes
from cls.applications.bioXasIM.scan_plugins import plugin_dir
from cls.applications.bioXasIM.scan_plugins.PositionerSSCAN import PositionerSSCAN
from cls.applications.bioXasIM.device_names import *
from cls.data_io.bioxas_im_data_io import BioxasDataIo


from cls.scanning.paramLineEdit import intLineEditParamObj, dblLineEditParamObj

from cls.utils.roi_utils import get_base_roi, get_base_energy_roi, make_spatial_db_dict, get_unique_roi_id, \
                    on_range_changed, on_npoints_changed, on_step_size_changed, on_start_changed, on_stop_changed, \
                    get_first_sp_db_from_wdg_com, on_center_changed, recalc_setpoints, widget_com_cmnd_types
from cls.scanning.bioxasTypes import scan_types, scan_panel_order, spatial_type_prefix
from cls.utils.roi_dict_defs import *
from cls.utils.dict_utils import dct_get, dct_put
from cls.utils.log import get_module_logger

_logger = get_module_logger(__name__)

class PositionerScanParam(ScanParamWidget):
    name = "Positioner Scan"
    idx = scan_panel_order.POSITIONER_SCAN
    type = scan_types.GENERIC_SCAN
    section_id = 'POSITIONER'
    axis_strings = ['%s Y microns', '%s X microns', '', '']
    #use the mode that adjusts the zoneplate by calculating the zpz using the A0 mod
    zp_focus_mode = zp_focus_modes.A0MOD
    data_file_pfx = MAIN_OBJ.get_datafile_prefix()
    plot_item_type = spatial_type_prefix.SEG

    data = {}

    def __init__(self, parent=None):
        ScanParamWidget.__init__(self, main_obj=MAIN_OBJ, data_io=BioxasDataIo, dflts=DEFAULTS)
        self._parent = parent
        uic.loadUi(os.path.join(plugin_dir,'positioner_scan.ui'), self)

        self.posner_dct = {}
        self.populate_positioner_cbox()

        self.loadScanBtn.clicked.connect(self.load_scan)
        self.posnerComboBox.currentIndexChanged.connect(self.positioner_changed)

        self.sscan_class = PositionerSSCAN()
        self.positioner = None


        self.sp_db = None
        self.load_from_defaults()
        self.init_sp_db()
        self.on_single_spatial_npoints_changed()

    def connect_paramfield_signals(self):

#         self.startXFld.returnPressed.connect(self.on_single_spatial_start_changed)
#         self.endXFld.returnPressed.connect(self.on_single_spatial_stop_changed)
#         self.npointsXFld.returnPressed.connect(self.on_single_spatial_npoints_changed)
#         self.stepXFld.returnPressed.connect(self.on_single_spatial_stepsize_changed)

        mtr_x = MAIN_OBJ.device(self.positioner)

        xllm = mtr_x.get_low_limit()
        xhlm = mtr_x.get_high_limit()

        rx = xhlm - xllm

        lim_dct = {}
        lim_dct['X'] = {'llm':xllm, 'hlm': xhlm, 'rng':rx}

        self.connect_param_flds_to_validator(lim_dct)

    def populate_positioner_cbox(self):
        devices = MAIN_OBJ.get_devices()
        idx = 0
        for posner in list(devices['POSITIONERS'].keys()):
            self.posnerComboBox.addItem(posner)
            self.posner_dct[posner] = idx
            idx += 1

    def init_sp_db(self):
        """
        init_sp_db standard function supported by all scan pluggins to initialize the local widget_com dict to whatever the
        GUI is currently displaying, this is usually called after the call to self.load_from_defaults()

        :returns: None

        """
        self.positioner = str(self.posnerComboBox.itemText(0))
        startx = float(str(self.startXFld.text()))
        stopx = float(str(self.endXFld.text()))
        dwell = float(str(self.dwellFld.text()))
        nx = int(str(self.npointsXFld.text()))
        sx = float(str(self.stepXFld.text()))
        #now create the model that this pluggin will use to record its params
        cx = (startx + stopx) * 0.5
        rx = stopx - startx
        x_roi = get_base_roi(SPDB_X, 'None', cx, rx, nx, sx)
        y_roi = get_base_roi(SPDB_Y, 'None', 0, 0, 0, enable=False)
        z_roi = get_base_roi(SPDB_Z, 'None', 0, 0, 0, enable=False)

        energy_pos = MAIN_OBJ.device(DNM_ENERGY).get_position()
        e_roi = get_base_energy_roi(SPDB_EV, DNM_ENERGY, energy_pos, energy_pos, 0, 1, dwell, None, enable=False )

        self.sp_db = make_spatial_db_dict(x_roi=x_roi, y_roi=y_roi, z_roi=z_roi, e_roi=e_roi)

    def check_scan_limits(self):
        ''' a function to be implemented by the scan pluggin that
        checks the scan parameters against the soft limits of the
        positioners, if all is well return true else false

        This function should provide an explicit error log msg to aide the user
        '''
        ret = False
        if(len(self.positioner) > 0):
            ret = self.check_start_stop_x_scan_limits(self.positioner)
        return(ret)


    def positioner_changed(self, idx):
        posner = str(self.posnerComboBox.currentText())
        #print '%s selected' % posner
        self.positioner = posner
        self.connect_paramfield_signals()

    def set_dwell(self, dwell):
        self.set_parm(self.dwellFld, dwell)
        self.update_data()

    def set_roi(self, roi):
        """
        set_roi standard function supported by all scan pluggins to initialize the GUI for this scan with values
        stored in the defaults library

        :param roi: is a standard dict returned from the call to DEFAULTS.get_defaults()
        :type roi: dict.

        :returns: None

        """
        #print 'det_scan: set_roi: ' , roi
        (cx, cy, cz, c0) = roi[CENTER]
        (rx, ry, rz, s0) = roi[RANGE]
        (nx, ny, nz, n0) = roi[NPOINTS]
        (sx, sy, sz, s0) = roi[ROI_STEP]

        if(DWELL in roi):
            self.set_parm(self.dwellFld, roi[DWELL])

        self.set_parm(self.startXFld, cx)
        self.set_parm(self.endXFld, rx)

        if(nx != None):
            self.set_parm(self.npointsXFld, nx, type='int', floor=2)

        if(sx != None):
            self.set_parm(self.stepXFld, sx, type='float', floor=0)


    def mod_roi(self, sp_db, do_recalc=True, sp_only=True):
        """
        sp_db is a widget_com dict
        The purpose of the mod_roi() function is to update the fields in the GUI with the correct values
        it can be called by either a signal from one of the edit fields (ex: self.startXFld) or
        by a signal from a plotter (via the main gui that is connected to the plotter) so that as a user
        grabs a region of interest marker in the plot and either moves or resizes it, those new center and size
        values will be delivered here and,  if required, the stepsizes will be recalculated


        :param sp_db: is a standard dict returned from the call to sm.stxm_control.stxm_utils.roi_utils.make_spatial_db_dict()
        :type sp_db: dict.

        :param do_recalc: selectively the STEP of the ROI's for X and Y can be recalculated if the number of points or range have changed
        :type do_recalc: flag.

        :returns: None

        """
        self.sp_db[SPDB_X][START] = sp_db[SPDB_X][START]
        self.sp_db[SPDB_X][STOP] = sp_db[SPDB_X][STOP]

        x_roi = self.sp_db[SPDB_X]
        e_rois = self.sp_db[SPDB_EV_ROIS]

        if(do_recalc):
            on_range_changed(x_roi)

        self.set_parm(self.startXFld, x_roi[START])
        self.set_parm(self.endXFld, x_roi[STOP])

        if(e_rois[0][DWELL] != None):
            self.set_parm(self.dwellFld, e_rois[0][DWELL])

        if(x_roi[NPOINTS] != None):
            self.set_parm(self.npointsXFld, x_roi[NPOINTS], type='int', floor=2)

        if(x_roi[ROI_STEP] != None):
            self.set_parm(self.stepXFld, x_roi[ROI_STEP], type='float', floor=0)


    def load_roi(self, wdg_com, append=False):
            """
            take a widget communications dict and load the plugin GUI with the spatial region, also
            set the scan subtype selection pulldown for point by point or line
            """

            #wdg_com = dct_get(ado_obj, ADO_CFG_WDG_COM)

            if(wdg_com[WDGCOM_CMND] == widget_com_cmnd_types.LOAD_SCAN):
                sp_db = get_first_sp_db_from_wdg_com(wdg_com)
                positioner = sp_db[SPDB_X][POSITIONER]

                if(dct_get(sp_db, SPDB_SCAN_PLUGIN_TYPE) != self.type):
                    return

                self.mod_roi(sp_db, do_recalc=False)

                idx = self.posner_dct[positioner]
                self.posnerComboBox.setCurrentIndex(idx)

            #emit roi_changed so that the plotter can be signalled to create the ROI shap items
            #self.roi_changed.emit(wdg_com)

#     def load_roi(self, wdg_com):
#         """
#         take a widget communications dict and load the plugin GUI with the spatial region, also
#         set the scan subtype selection pulldown for point by point or line
#         """
#
#         if(wdg_com[WDGCOM_CMND] == widget_com_cmnd_types.LOAD_SCAN):
#             sp_db = get_first_sp_db_from_wdg_com(wdg_com)
#             positioner = sp_db[SPDB_X][POSITIONER]
#             if(dct_get(sp_db, SPDB_SCAN_PLUGIN_TYPE) != scan_types.GENERIC_SCAN):
#                 return
#
#             idx = self.posner_dct[positioner]
#             self.posnerComboBox.setCurrentIndex(idx)

    def update_last_settings(self):
        """ update the 'default' settings that will be reloaded when this scan pluggin is selected again
        """
        x_roi = self.sp_db[SPDB_X]
        e_rois = self.sp_db[SPDB_EV_ROIS]

        DEFAULTS.set('SCAN.POSITIONER.CENTER', (x_roi[START], 0, 0, 0))
        DEFAULTS.set('SCAN.POSITIONER.RANGE', (x_roi[STOP], 0, 0, 0))
        DEFAULTS.set('SCAN.POSITIONER.NPOINTS', (x_roi[NPOINTS], 0, 0, 0))
        DEFAULTS.set('SCAN.POSITIONER.STEP', (x_roi[ROI_STEP], 0, 0, 0))
        DEFAULTS.set('SCAN.POSITIONER.DWELL', e_rois[0][DWELL])
        DEFAULTS.update()

    def update_data(self):
        """
        This is a standard function that all scan pluggins have that is called to
        get the data from the pluggins UI widgets and write them into a dict returned by
        get_base_scanparam_roi(), this dict is emitted by all scan pluggins to be used by
        the scan classes configure() functions

        :returns: None

        """
        #update local widget_com dict
        wdg_com = self.update_single_spatial_wdg_com(positioner=self.positioner)
        self.update_last_settings()

        return(wdg_com)

