# -*- coding: utf-8 -*-
"""
/***************************************************************************
 BHCgeo_QGIS
                                 A QGIS plugin
 Calculates the Climatic Water Balance in each pixel
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2019-06-22
        git sha              : $Format:%H$
        copyright            : (C) 2019 by Carvalho Neto, R.M./UFSM; Cruz, J.C./UFSM; Cruz, R.C./UNIPAMPA
        email                : romariocarvalho@hotmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt5 import QtGui
from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QFileDialog, QDialog, QProgressBar
from PyQt5.QtWidgets import *
from qgis.utils import iface
from qgis.core import Qgis, QgsProject, QgsTask, QgsApplication
import gdal, osr, io
import numpy as np 
from math import *
# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .BHCgeoQGIS_dialog import BHCgeo_QGISDialog
import os.path


class BHCgeo_QGIS:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'bhcgeoqgis_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&BHCgeo')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('BHCgeo_QGIS', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToRasterMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/BHCgeoQGIS/figBHC.png'
        self.add_action(
            icon_path,
            text=self.tr(u'BHCgeo'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginRasterMenu(
                self.tr(u'&BHCgeo'),
                action)
            self.iface.removeToolBarIcon(action)

    def select_output_file(self):      
        filename = QFileDialog.getExistingDirectory(BHCgeo_QGIS.dlg, ("Choose the output folder"))
        BHCgeo_QGIS.dlg.lineEdit.setText(filename)

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            BHCgeo_QGIS.dlg = BHCgeo_QGISDialog()
            BHCgeo_QGIS.dlg.pushButton.clicked.connect(self.select_output_file)
        
        BHCgeo_QGIS.dlg.comboBox.clear()                          
        
        # meses_list = ["January","February","March","April",
                        # "May","June","July","August","September",
                        # "October","November","December"] 
        meses_list = [QCoreApplication.translate('self.dlg.comboBox', "January"),
                        QCoreApplication.translate('self.dlg.comboBox', "February"),
                        QCoreApplication.translate('self.dlg.comboBox', "March"),
                        QCoreApplication.translate('self.dlg.comboBox', "April"),
                        QCoreApplication.translate('self.dlg.comboBox', "May"),
                        QCoreApplication.translate('self.dlg.comboBox', "June"),
                        QCoreApplication.translate('self.dlg.comboBox', "July"),
                        QCoreApplication.translate('self.dlg.comboBox', "August"),
                        QCoreApplication.translate('self.dlg.comboBox', "September"),
                        QCoreApplication.translate('self.dlg.comboBox', "October"),
                        QCoreApplication.translate('self.dlg.comboBox', "November"),
                        QCoreApplication.translate('self.dlg.comboBox', "December")] 

        BHCgeo_QGIS.dlg.comboBox.addItems(meses_list)
        
        # show the dialog
        BHCgeo_QGIS.dlg.show()
        # Run the dialog event loop
        result = BHCgeo_QGIS.dlg.exec_()
        # See if OK was pressed
        if result:
            BHCgeo_QGIS.progress_bar = ProgessBar()
            BHCgeo_QGIS.progress_bar.show()
            


class HeavyTask(QgsTask):
    """Here we subclass QgsTask"""
    def __init__(self, desc):
        QgsTask.__init__(self, desc)


    def array2raster(self,rasterfn,newRasterfn,array):
        raster = gdal.Open(rasterfn) #raster modelo
        geotransform = raster.GetGeoTransform()
        originX = geotransform[0] 
        originY = geotransform[3]
        pixelWidth = self.instantiatePixelWidth
        pixelHeight = self.instantiatePixelHeight
        cols = raster.RasterXSize
        rows = raster.RasterYSize

        driver = gdal.GetDriverByName('GTiff')
        outRaster = driver.Create(newRasterfn, cols, rows, 1, gdal.GDT_Float32)
        outRaster.SetGeoTransform((originX, pixelWidth, 0, originY, 0, pixelHeight))
        outband = outRaster.GetRasterBand(1)
        outband.WriteArray(array)
        outband.SetNoDataValue(self.NoData) #nao insere valor de NoData, mas sim, escolhe um valor dentre os existentes
        outRasterSRS = osr.SpatialReference()
        outRasterSRS.ImportFromWkt(raster.GetProjectionRef())
        outRaster.SetProjection(outRasterSRS.ExportToWkt())
        outband.FlushCache()
        return newRasterfn

    def run(self):
        """This function is where you do the 'heavy lifting' or implement
        the task which you want to run in a background thread. This function 
        must return True or False and should only interact with the main thread
        via signals"""
        
        percent = 0
        self.setProgress(percent)

        BHCgeo_QGIS.pastaSelecionada = BHCgeo_QGIS.dlg.lineEdit.text()
        self.diretorio = BHCgeo_QGIS.pastaSelecionada+"\\"
         
        listaMesDesordenada = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'] 
        self.nomeMes = []
        BHCgeo_QGIS.mesEscolhidoIndex = BHCgeo_QGIS.dlg.comboBox.currentIndex()   # <-----

        cont = BHCgeo_QGIS.mesEscolhidoIndex
        for mes in range(len(listaMesDesordenada) - BHCgeo_QGIS.mesEscolhidoIndex):
            self.nomeMes.append(listaMesDesordenada[cont])
            cont += 1
        cont = 0
        for mes in range(BHCgeo_QGIS.mesEscolhidoIndex):
            self.nomeMes.append(listaMesDesordenada[cont]) 
            cont += 1
        #-----------------------------------------------------------

        self.NoData = -9999
        CAD_raster = gdal.Open(self.diretorio+"cad.tif")   
        bandaUnicaCAD = CAD_raster.GetRasterBand(1)
        bandaUnicaCAD.SetNoDataValue(self.NoData)
        CAD_array = np.array(bandaUnicaCAD.ReadAsArray())
        CAD_list = []
        CAD_list.append(CAD_array.tolist())
        ETP_list = [[] for mes in self.nomeMes]
        P_list = [[] for mes in self.nomeMes]

        contMes = 0
        for mes in self.nomeMes:
            ETP_raster = gdal.Open(self.diretorio+"etp"+mes+".tif")   
            bandaUnicaETP = ETP_raster.GetRasterBand(1)
            bandaUnicaETP.SetNoDataValue(self.NoData)
            ETP_array = np.array(bandaUnicaETP.ReadAsArray()) 
            ETP_listMes = ETP_array.tolist()
            ETP_list[contMes].append(ETP_listMes)
            P_raster = gdal.Open(self.diretorio+"p"+mes+".tif")   
            bandaUnicaP = P_raster.GetRasterBand(1)
            bandaUnicaP.SetNoDataValue(self.NoData)
            P_array = np.array(bandaUnicaP.ReadAsArray()) 
            P_listMes = P_array.tolist()
            P_list[contMes].append(P_listMes)
            contMes += 1
        
        percent = 10
        self.setProgress(percent)
        amount = len(self.nomeMes)
        # ---------------- Verificando as condicoes para fazer os calculos ---------------------------

        for mes in self.nomeMes:
            #--- calculate a aprox size to put in the progress bar  
            bit = (20-percent) / amount   # max until this point - last point / len
            percent += bit # beggins the point at 10% 
            self.setProgress(percent)
            #-------------------------------------------------------------
            CAD_raster = gdal.Open(self.diretorio+"cad.tif")
            ETP_raster = gdal.Open(self.diretorio+"etp"+mes+".tif") 
            P_raster = gdal.Open(self.diretorio+"p"+mes+".tif")
            assert CAD_raster.RasterXSize == ETP_raster.RasterXSize == P_raster.RasterXSize 
            assert CAD_raster.RasterYSize == ETP_raster.RasterYSize == P_raster.RasterYSize 

        #-------------------- Substituindo valores de CAD = 0 por NoData ------------------------------

        for matriz in range(len(CAD_list)):
            for row in range(len(CAD_list[matriz])):
                for i in range(len(CAD_list[matriz][row])):
                    if CAD_list[matriz][row][i] == 0:
                        CAD_list[matriz][row].pop(i)    # retira o cad 0 e substitui por NODATA
                        CAD_list[matriz][row].insert(i,self.NoData)            

        #-------------------- Retirando as linhas que vem do formato array ------------------------------

        CADFloatAll = []
        ETPFloatAll = [[] for mes in self.nomeMes]
        PFloatAll = [[] for mes in self.nomeMes]

        for matriz in range(len(CAD_list)):
            for row_cont in range(len(CAD_list[matriz])):
                for item in range(len(CAD_list[matriz][row_cont])):
                    CADFloatAll.append(CAD_list[matriz][row_cont][item])

        for mes in range(len(self.nomeMes)):
            for matriz in range(len(ETP_list[mes])):     
                for row_cont in range(len(ETP_list[mes][matriz])):
                    for item in range(len(ETP_list[mes][matriz][row_cont])):
                        ETPFloatAll[mes].append(ETP_list[mes][matriz][row_cont][item])
                        PFloatAll[mes].append(P_list[mes][matriz][row_cont][item])
        
        percent = 20
        self.setProgress(percent)
        #--------------------------- Fazendo o calculo ---------------------------------------------

        ARM = [[] for i in range(len(self.nomeMes))]
        ETR = [[] for i in range(len(self.nomeMes))]
        B = [[] for i in range(len(self.nomeMes))]

        for mes in range(amount):
            #--- calculate a aprox size to put in the progress bar  
            bit = (50-percent) / amount   # max until this point - last point / len
            percent += bit # beggins the point at 10% 
            self.setProgress(percent)
            #-------------------------------------------------------------
            if mes == 0:  # primeiro mes
                for cell in range(len(CADFloatAll)):
                    if PFloatAll[mes][cell] == self.NoData or ETPFloatAll[mes][cell] == self.NoData:
                        ARM[mes].append(self.NoData) #nao faz o calculo para NoData
                    else:
                        ARM[mes].append(CADFloatAll[cell])

                cont_i = 0
                for i in PFloatAll[mes]:
                    if CADFloatAll[cont_i] == self.NoData or PFloatAll[mes][cont_i] == self.NoData or ETPFloatAll[mes][cont_i] == self.NoData:
                        B[mes].append(self.NoData)     #nao faz o calculo para self.NoData
                        ETR[mes].append(self.NoData)
                        cont_i += 1
                        
                    elif PFloatAll[mes][cont_i] - ETPFloatAll[mes][cont_i] > 0: #excesso
                        if ARM[mes][cont_i] + (PFloatAll[mes][cont_i] - ETPFloatAll[mes][cont_i]) >= CADFloatAll[cont_i]:
                            B[mes].append(PFloatAll[mes][cont_i] - ETPFloatAll[mes][cont_i]) #sempre para o mes zero B = Pi-ETPi
                            ETR[mes].append(ETPFloatAll[mes][cont_i])
                            cont_i += 1
                        else:
                            assert ARM[mes][cont_i] + (PFloatAll[mes][cont_i] - ETPFloatAll[mes][cont_i]) >= CADFloatAll[cont_i]#, print("\n"+
                                #"  ---> COMECOU COM MES ERRADO! O arm anterior deve ser igual a CAD quando roda o modelo a primeira vez! <---  ")
                            break
                            
                    else: # defict   ---> teoricamente nao deveria ter essa possibilidade no primeiro mes,pois deve ser escolhido um mes com P>ETP para iniciar
                        form = ARM[mes][cont_i] * exp((PFloatAll[mes][cont_i] - ETPFloatAll[mes][cont_i]) / CADFloatAll[cont_i])
                        if form > 0: 
                            # Neste primeiro mes, form = ARM do mes em questao (mes zero) e ARM[mes] == ARM do mes anterior
                            B[mes].append((PFloatAll[mes][cont_i] + (ARM[mes][cont_i] - form)) - ETPFloatAll[mes][cont_i]) 
                            ARM_mes_anterior = ARM[mes][cont_i] #guarda o valor de arm que vai ser atualizado
                            ARM[mes].pop(cont_i)
                            ARM[mes].insert(cont_i,form)
                            ETR[mes].append(PFloatAll[mes][cont_i] + (ARM_mes_anterior - form)) #teoricamente nao deveria ter ETR no primeiro mes
                            cont_i += 1                                                         #pois deve ser escolhido um mes com P>ETP para iniciar
                        else:
                            assert form > 0#, print("  ---> ERRO MATEMATICO! Nao pode acontecer tal resultado. <---  ")
                            break
                            
            else:  # outros meses
                cont_i = 0
                for i in PFloatAll[mes]:
                    if CADFloatAll[cont_i] == self.NoData or PFloatAll[mes][cont_i] == self.NoData or ETPFloatAll[mes][cont_i] == self.NoData:
                        B[mes].append(self.NoData)     #nao faz o calculo para NoData
                        ARM[mes].append(self.NoData)     #nao faz o calculo para NoData
                        ETR[mes].append(self.NoData)
                        cont_i += 1
                        
                    elif PFloatAll[mes][cont_i] - ETPFloatAll[mes][cont_i] > 0: #excesso
                        if ARM[mes-1][cont_i] + (PFloatAll[mes][cont_i] - ETPFloatAll[mes][cont_i]) >= CADFloatAll[cont_i]:
                            ARM[mes].append(CADFloatAll[cont_i])
                            ETR[mes].append(ETPFloatAll[mes][cont_i])
                            B[mes].append(ARM[mes-1][cont_i] + (PFloatAll[mes][cont_i] - ETPFloatAll[mes][cont_i]) - CADFloatAll[cont_i])
                            cont_i += 1
                        else:
                            ARM[mes].append(ARM[mes-1][cont_i] + (PFloatAll[mes][cont_i] - ETPFloatAll[mes][cont_i]))
                            ETR[mes].append(ETPFloatAll[mes][cont_i])
                            B[mes].append(0)
                            cont_i += 1
                            
                    else: # defict
                        form = ARM[mes-1][cont_i] * exp((PFloatAll[mes][cont_i] - ETPFloatAll[mes][cont_i]) / CADFloatAll[cont_i])
                        if form > 0:
                            ARM[mes].append(form)
                            ETR[mes].append(PFloatAll[mes][cont_i] + (ARM[mes-1][cont_i]-ARM[mes][cont_i]))
                            B[mes].append((PFloatAll[mes][cont_i] + (ARM[mes-1][cont_i]-ARM[mes][cont_i])) - ETPFloatAll[mes][cont_i])
                            cont_i += 1
                        else:
                            assert form > 0#, print("  ---> ERRO MATEMATICO! Nao pode acontecer tal resultado. <---  ")
                            break
        percent = 50
        self.setProgress(percent)
        if BHCgeo_QGIS.dlg.checkBox_PR.isChecked():    # <-----

            # ---------------------------- PROVA REAL -------------------------------------

            listaRelatorio = []                
            texto = QCoreApplication.translate('report', '''The Verification Proof checks if the following conditions were respected, in each pixel:
            
    Sum(ETP) = Sum(ETR)+Sum(DEF)
    Sum(P) = Sum(ETR)+Sum(EXC)
    Sum(Alt) = 0

    Where DEF(Water Deficit) = B negative, EXC(Water Excess) = B positive and Alt
is the alteration sufered by ARM, from one month to the next.

    If these conditions are not met, the report will point out the first pixel
where the error occurred, with a tolerance of 0.9 mm. Therefore, it is very likely
that there are other pixels with the same error. This means that another month 
should be chosen to be the first in the Climatic Water Balance (BHC) calculations.

    The month prior to the one chosen to start the BHC should have its ground water 
storage totally filled, this means that in the previous month, ARM must be equal to 
CAD, that is, the month prior to the first (and preferably the first month as well)
should not be a month of water deficit.

    If you do not have an idea when to start the BHC, you should run several tests 
(Verification Proof) to identify when to start and thus produce the most reliable 
outputs.

    If it is a very large and/or very heterogeneous area, climatologically, and all
Verification Proofs found out errors, the inputs are suggested to be fragmented in 
smaller areas to better represent their climatological characteristics.


    ******************************* REPORT ******************************
            ''')

            listaRelatorio.append(texto)

            somatorioP = [ [] for cell in CADFloatAll ]  #somatorio por pixel
            somatorioETP = [ [] for cell in CADFloatAll ]
            somatorioETR = [ [] for cell in CADFloatAll ]
            somatorioDEF = [ [] for cell in CADFloatAll ]
            somatorioEXC = [ [] for cell in CADFloatAll ]
            somatorioAlt = [ [] for cell in CADFloatAll ]

            amount_cell = len(CADFloatAll)
            for cell in range(amount_cell):
                #--- calculate a aprox size to put in the progress bar  
                bit = (60-percent) / amount_cell   # max until this point - last point / len
                percent += bit # beggins the point at 10% 
                self.setProgress(percent)
                #-------------------------------------------------------------
                for mes in range(len(self.nomeMes)):
                    if ETR[mes][cell] == self.NoData:  # B[mes][cell] == NoData or PFloatAll[mes][cell] == NoData or ETPFloatAll[mes][cell] == NoData:
                        somatorioP[cell].append(self.NoData)
                        somatorioETP[cell].append(self.NoData)
                        somatorioETR[cell].append(self.NoData)
                        somatorioEXC[cell].append(self.NoData)
                        somatorioDEF[cell].append(self.NoData)
                        somatorioAlt[cell].append(self.NoData)
                    else:
                        somatorioP[cell].append(PFloatAll[mes][cell])
                        somatorioETP[cell].append(ETPFloatAll[mes][cell])
                        somatorioETR[cell].append(ETR[mes][cell])
                        somatorioAlt[cell].append(ARM[mes][cell]-ARM[mes-1][cell])

                        if B[mes][cell] > 0:
                            somatorioEXC[cell].append(B[mes][cell])
                        else:
                            somatorioDEF[cell].append(B[mes][cell]) 

            self.setProgress(60)

            for cell in range(len(CADFloatAll)):
                #--- calculate a aprox size to put in the progress bar  
                bit = (70-percent) / amount_cell   # max until this point - last point / len
                percent += bit # beggins the point at 10% 
                self.setProgress(percent)
                #-------------------------------------------------------------
                if self.NoData in somatorioETR[cell]: # pois ETR eh saida com NoData nos lugares certos
                    pass
                else:
                    arredondandoSomETP = sum(somatorioETP[cell])
                    arredondandoSomP = sum(somatorioP[cell])
                    arredondandoSomETR = sum(somatorioETR[cell])
                    arredondandoSomDEF = abs(sum(somatorioDEF[cell]))
                    arredondandoSomEXC = sum(somatorioEXC[cell])
                    arredondandoSomAlt = sum(somatorioAlt[cell])

                    if arredondandoSomETP == arredondandoSomETR + arredondandoSomDEF:
                        erro = "SEM ERRO"
                    elif abs(arredondandoSomETP - (arredondandoSomETR + arredondandoSomDEF)) < 1: #limite aceitavel, em mm, para fins de arredondamento
                        erro = "SEM ERRO"
                    else: 
                        mensagemRelatorio = ("\nPixel: "+str(cell)+"\n"+
                            QCoreApplication.translate("mensagemRelatorio","Sum(ETP): ")+
                            str(arredondandoSomETP)+"\n"+
                            QCoreApplication.translate("mensagemRelatorio","Sum(ETR)+Sum(DEF): ")+
                            str(arredondandoSomETR+arredondandoSomDEF)+"\n\n"+
                            QCoreApplication.translate("mensagemRelatorio", 
                            "In this pixel, the Verification Proof found a possible error. Choose another month to start with."))
                        listaRelatorio.append(mensagemRelatorio+"\n")
                        erro = "ERRO"
                        break
                    if arredondandoSomP == arredondandoSomETR + arredondandoSomEXC:
                        erro = "SEM ERRO"
                    elif abs(arredondandoSomP - (arredondandoSomETR + arredondandoSomEXC)) < 1: #limite aceitavel, em mm, para fins de arredondamento
                        erro = "SEM ERRO"
                    else: 
                        mensagemRelatorio = ("\nPixel: "+str(cell)+"\n"+
                            QCoreApplication.translate("mensagemRelatorio","Sum(P): ")+
                            str(arredondandoSomP)+"\n"+
                            QCoreApplication.translate("mensagemRelatorio","Sum(ETR)+Sum(EXC): ")+
                            str(arredondandoSomETR+arredondandoSomEXC)+"\n\n"+
                            QCoreApplication.translate("mensagemRelatorio", 
                            "In this pixel, the Verification Proof found a possible error. Choose another month to start with."))
                        listaRelatorio.append(mensagemRelatorio+"\n")
                        erro = "ERRO"
                        break
                    if arredondandoSomAlt == 0:
                        erro = "SEM ERRO"
                    elif arredondandoSomAlt < 1:
                        erro = "SEM ERRO"
                    else:
                        mensagemRelatorio = ("\nPixel: "+str(cell)+"\n"+
                            QCoreApplication.translate("mensagemRelatorio","Sum(Alt): ")+
                            str(arredondandoSomAlt)+"\n\n"+
                            QCoreApplication.translate("mensagemRelatorio",
                            "In this pixel, the Verification Proof found a possible error. Choose another month to start with"))
                        listaRelatorio.append(mensagemRelatorio+"\n")
                        erro = "ERRO"
                        break                            
                    
            if erro == "ERRO":
                mensagemRelatorio = QCoreApplication.translate("mensagemRelatorio",
'''\n--> The Verification Proof found out, in at least one pixel, the existence of a possible error.

        ***** CONSIDER GETTING STARTED WITH ANOTHER MONTH *****''')
                listaRelatorio.append(mensagemRelatorio+"\n")
            elif erro == "SEM ERRO":
                mensagemRelatorio = QCoreApplication.translate("mensagemRelatorio",
'''\n--> The Verification Proof found out that the conditions of equality, according to the formulas,
were maintained in all pixels.''')
                listaRelatorio.append(mensagemRelatorio+"\n")
            else:
                mensagemRelatorio = str(erro) # nunca deve acontecer
                listaRelatorio.append(mensagemRelatorio+"\n")
                
            abrirRelatorio = io.open(self.diretorio+QCoreApplication.translate("mensagemRelatorio",
                "Report.txt"), mode="w", encoding="utf-8")
            for i in listaRelatorio:
                abrirRelatorio.write(unicode(i))
            abrirRelatorio.close()
            
        # -------------------- Criando os Rasters Finais -------------------------------
        percent = 70
        self.setProgress(percent)
        B_array = [[[] for rows in CAD_array] for mes in self.nomeMes]  # cria os espacos para os rows que tem nos arquivos de entrada, para virar array
        ARM_array = [[[] for rows in CAD_array] for mes in self.nomeMes]
        ETR_array = [[[] for rows in CAD_array] for mes in self.nomeMes]

        for mes in range(len(self.nomeMes)):
            item_cont = 0
            for row in range(len(CAD_array)):
                for item in range(len(CAD_array[row])):
                    B_array[mes][row].append(B[mes][item_cont])
                    ARM_array[mes][row].append(ARM[mes][item_cont])
                    ETR_array[mes][row].append(ETR[mes][item_cont])
                    item_cont += 1 

        dataset = gdal.Open(self.diretorio+'cad.tif') #raster modelo de tamanho pixel
        geotransform = dataset.GetGeoTransform()
        if geotransform:
            self.instantiatePixelWidth = geotransform[1]
            self.instantiatePixelHeight = geotransform[5]

        rasterModelo = self.diretorio+'cad.tif'  # usa os parametros do raster modelo

        if BHCgeo_QGIS.dlg.checkBox_B.isChecked():   # <-----
            contMes = 0
            for mes in self.nomeMes:
                rasterSaidaB = self.diretorio+'b'+mes+'.tif'
                my_array_B = np.array(B_array[contMes])
                self.saida_BHC = self.array2raster(rasterModelo, rasterSaidaB, my_array_B)
                #iface.addRasterLayer(saida_BHC)  #tem que adicionar .self para que funcione, pois iface foi referenciado la em cima
                contMes += 1
                #--- calculate a aprox size to put in the progress bar  
                bit = (70-percent) / amount   # max until this point - last point / len
                percent += bit # beggins the point at 10% 
                self.setProgress(percent)
                #-------------------------------------------------------------
        
        percent = 80
        self.setProgress(percent)
        if BHCgeo_QGIS.dlg.checkBox_ETR.isChecked():   # <-----
            contMes = 0
            for mes in self.nomeMes:
                rasterSaidaETR = self.diretorio+'etr'+mes+'.tif'
                my_array_ETR = np.array(ETR_array[contMes])
                self.saida_ETR = self.array2raster(rasterModelo, rasterSaidaETR, my_array_ETR)
                #iface.addRasterLayer(saida_ETR)     #tem que adicionar .self para que funcione, pois iface foi referenciado la em cima
                contMes += 1
                #--- calculate a aprox size to put in the progress bar  
                bit = (80-percent) / amount   # max until this point - last point / len
                percent += bit # beggins the point at 10% 
                self.setProgress(percent)
                #-------------------------------------------------------------
        
        percent = 90
        self.setProgress(percent)
        if BHCgeo_QGIS.dlg.checkBox_ARM.isChecked():   # <-----
            contMes = 0
            for mes in self.nomeMes:
                rasterSaidaARM = self.diretorio+'arm'+mes+'.tif'
                my_array_ARM = np.array(ARM_array[contMes])
                self.saida_ARM = self.array2raster(rasterModelo, rasterSaidaARM, my_array_ARM)
                #iface.addRasterLayer(saida_ARM)     #tem que adicionar .self para que funcione, pois iface foi referenciado la em cima
                contMes += 1
                #--- calculate a aprox size to put in the progress bar  
                bit = (99-percent) / amount   # max until this point - last point / len
                percent += bit # beggins the point at 10% 
                self.setProgress(percent)
                #-------------------------------------------------------------
                
        percent = 99
        self.setProgress(percent)
        return True


    def finished(self, result):
        """This function is called automatically when the task is completed and is
        called from the main thread so it is safe to interact with the GUI etc here"""
        if result is False:
            iface.messageBar().pushMessage(QCoreApplication.translate('Task message','Task was cancelled'))
        else:
            iface.messageBar().clearWidgets()
            for mes in self.nomeMes:
                if BHCgeo_QGIS.dlg.checkBox_B.isChecked(): 
                    iface.addRasterLayer(self.diretorio+'b'+mes+'.tif')
                if BHCgeo_QGIS.dlg.checkBox_ETR.isChecked():
                    iface.addRasterLayer(self.diretorio+'etr'+mes+'.tif')
                if BHCgeo_QGIS.dlg.checkBox_ARM.isChecked():  
                    iface.addRasterLayer(self.diretorio+'arm'+mes+'.tif')
                percent = 100
                self.setProgress(percent)
                iface.messageBar().pushMessage(QCoreApplication.translate('Task message','Complete'))
                #ProgessBar.btn_cancel.setEnabled(False)



class ProgessBar(QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.resize(310, 140)
        self.lbl_info = QLabel('Info:', self) 
        self.lbl_info.move(40, 25) # label with Info
        self.edit_info = QLineEdit(self)
        self.edit_info.resize(170, 20)
        self.edit_info.move(100, 20) # Show changing messages
        self.prog = QProgressBar(self)
        self.prog.resize(230, 30)
        self.prog.move(40, 55) 
        self.newTask('BHCgeo')
        btn_close = QPushButton(QCoreApplication.translate('Task message','Close'),self)
        btn_close.move(190, 100)
        btn_close.clicked.connect(self.close_win)
        # ProgessBar.btn_cancel = QPushButton('Cancel Task', self)
        # ProgessBar.btn_cancel.move(40, 100)
        # ProgessBar.btn_cancel.clicked.connect(self.cancelTask)


    def newTask(self, message_task_description):
        """Create a task and add it to the Task Manager"""
        self.task = HeavyTask(message_task_description)
        #connect to signals from the background threads to perform gui operations
        #such as updating the progress bar
        self.task.begun.connect(lambda: self.edit_info.setText(QCoreApplication.translate("Task message","Calculating...")))
        self.task.progressChanged.connect(lambda: self.prog.setValue(self.task.progress()))
        self.task.progressChanged.connect(lambda: self.setProgressBarMessages(self.task.progress()))
        self.task.taskCompleted.connect(lambda: self.edit_info.setText(QCoreApplication.translate('Task message','Complete')))
        self.task.taskTerminated.connect(self.TaskCancelled)
        QgsApplication.taskManager().addTask(self.task)


    def TaskCancelled(self):
        self.prog.setValue(0)
        self.edit_info.setText(QCoreApplication.translate('Task message','Task Cancelled'))


    def close_win(self):
        self.close()


    def setProgressBarMessages(self, val):
    # --- Progress bar in the QGIS user messages (top)
        if val <= 30:
            message = QCoreApplication.translate("Task message","Starting...")
            iface.messageBar().pushMessage(message)
        elif val < 60:
            message = QCoreApplication.translate("Task message","Calculating water balance...")
            iface.messageBar().pushMessage(message)
        elif val < 100:
            message = QCoreApplication.translate("Task message","Preparing final raster...")
            iface.messageBar().pushMessage(message)
        # elif val == 100:
        #     iface.messageBar().clearWidgets()


    # def cancelTask(self):
    #     self.task.cancel()