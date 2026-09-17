#!/usr/bin/env python3
"""Render current QML previews with real offline demo geography.

Requires PySide6 (development only). Quickshell host surfaces and the network
service are replaced with local fixtures; plugin UI files are copied unchanged.
No credentials or network access are used. Run from any working directory:
QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=2 python3 tools/render_previews.py
"""


def main():
    import os
    import tempfile
    from pathlib import Path

    os.chdir(Path(__file__).resolve().parent.parent)
    import shutil
    from pathlib import Path

    scratch = tempfile.TemporaryDirectory(prefix="vessel-previews-")
    root = Path(scratch.name)
    for name in [
        "Widget.qml",
        "BoatIcon.qml",
        "Radar.qml",
        "Robot.qml",
        "Model.js",
        "qmldir",
        "Keyboard.js",
        "KeyboardIcon.qml",
        "KeyboardHelp.qml",
        "SettingsForm.qml",
    ]:
        shutil.copy(name, root / name)

    def put(name, text):
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    put(
        "VesselService.qml",
        """pragma Singleton
    import QtQuick
    Item {
     property var report: ({status:"LIVE", location:"Genoa · Italy",radius:25,total:1,demo:true})
     property var ships: [{mmsi:"123",name:"VESSEL DEMO",destination:"GENOA",distance:4,bearing:70,speed:8,type:"Cargo",timeSource:"Received",lastSeen:Date.now()/1000,stale:false,lat:44.3,lon:8.9}]
     property var basemap: ({available:false,polygons:[],coastlines:[],cities:[]})
     property var preferences: ({unit:"nm"})
     property bool paused: false
     function attach(s) {} function detach() {} function configure(s) {} function restart() {} function loadSettings() {} function togglePaused() {paused=!paused}
    }""",
    )
    put(
        "qs/Commons/qmldir",
        "module qs.Commons\nsingleton Color 1.0 Color.qml\nsingleton Style 1.0 Style.qml\n",
    )
    put(
        "qs/Commons/Color.qml",
        'pragma Singleton\nimport QtQuick\nQtObject { property color foreground:"#dedbd0"; property color background:"#182125"; property color accent:"#d4a86a"; property color muted:"#8e9b9e" }',
    )
    put(
        "qs/Commons/Style.qml",
        "pragma Singleton\nimport QtQuick\nQtObject { function space(n) {return n;} }",
    )
    put(
        "qs/Ui/qmldir",
        "module qs.Ui\nBarWidget 1.0 BarWidget.qml\nWidgetButton 1.0 WidgetButton.qml\nKeyboardPanel 1.0 KeyboardPanel.qml\nPanelKeyCatcher 1.0 PanelKeyCatcher.qml\n",
    )
    put(
        "qs/Ui/BarWidget.qml",
        "import QtQuick\nItem {property string moduleName; property var bar:null; property var settings: ({}); property bool vertical:false}",
    )
    put(
        "qs/Ui/WidgetButton.qml",
        'import QtQuick\nItem {property var bar; property string text; property bool labelVisible; property bool hasVisualContent; property real fixedWidth; property real scaledHorizontalMargin:4; property color foreground:"white"; property string tooltipText; property bool dimmed; signal pressed(int b); implicitWidth:28; implicitHeight:28}',
    )
    put(
        "qs/Ui/KeyboardPanel.qml",
        """import QtQuick
    Window {
     property var anchorItem; property var owner; property var bar; property bool open; property var focusTarget
     property real contentWidth; property real contentHeight
     width:contentWidth; height:contentHeight; visible:open; color:"#182125"
     function fittedContentWidth(n) {return n;} function fittedContentHeight(n) {return Math.min(n,850);}
    }""",
    )
    put(
        "qs/Ui/PanelKeyCatcher.qml",
        "import QtQuick\nItem { property bool blocked; signal closeRequested(); signal returnRequested() }",
    )
    put(
        "Quickshell/qmldir",
        "module Quickshell\nFloatingWindow 1.0 FloatingWindow.qml\n",
    )
    put(
        "Quickshell/FloatingWindow.qml",
        "import QtQuick\nWindow { property real implicitWidth; property real implicitHeight; property size minimumSize; width:implicitWidth; height:implicitHeight }",
    )
    import json
    import sys
    import time
    from pathlib import Path

    from PySide6.QtCore import QMetaObject, QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest

    sys.path.insert(0, str(Path.cwd() / "backend"))
    import basemap
    from ais import Fleet
    from geometry import GENOA
    from vessel import populate_demo

    base = root
    import shutil

    shutil.copy("Widget.qml", base / "Widget.qml")
    fleet = Fleet(*GENOA, 25)
    now = time.time()
    populate_demo(fleet, 0, now)
    report = dict(
        status="DEMO",
        location="Genoa (Italy) · simulated traffic",
        radius=25,
        demo=True,
        **fleet.snapshot(now),
    )
    geo = basemap.build(*GENOA, 25)
    service = """pragma Singleton
    import QtQuick
    Item {
     property var report: REPORT
     property var ships: report.ships
     property var basemap: MAP
     property var preferences: ({provider:"openwaters",hasOpenwatersKey:false,unit:"nm",radiusNm:25,cityName:"Genoa",latitude:44.4056,longitude:8.9463,autoLocation:false,hasApiKey:true,demo:true})
     property bool paused:false
     property bool searchingCity:false
     property var cityResults:[]
     property string cityError:""
     property string settingsError:""
     property bool saving:false
     signal settingsSaved()
     function attach(s) {} function detach() {} function configure(s) {} function restart() {} function loadSettings() {}
     function clearCitySearch() {} function searchCity(t) {} function saveSettings(v) {}
     function togglePaused() {paused=!paused}
    }""".replace("REPORT", json.dumps(report)).replace("MAP", json.dumps(geo))
    (base / "VesselService.qml").write_text(service)
    (base / "qs/Ui/BarWidget.qml").write_text(
        'import QtQuick\nItem {property string moduleName; property QtObject bar: QtObject {property string fontFamily:"Menlo"}; property var settings: ({}); property bool vertical:false}'
    )
    (base / "Main.qml").write_text(
        'import QtQuick\nimport qs.Commons\nWindow {property var previewColors: Color; width:32;height:32;visible:true; Widget {objectName:"widget"}}'
    )
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(base))
    engine.load(QUrl.fromLocalFile(str(base / "Main.qml")))
    assert engine.rootObjects()
    top = engine.rootObjects()[0]
    root = top.findChild(QObject, "widget")
    windows = app.allWindows()

    def invoke(name):
        QMetaObject.invokeMethod(root, name)
        QTest.qWait(150)

    def window():
        return next(w for w in windows if w.isVisible() and w.width() > 100)

    def shot(name):
        QTest.qWait(200)
        surface = window()
        assert isinstance(surface, QQuickWindow)
        assert surface.grabWindow().save(str(Path.cwd() / name))

    root.setProperty("selectedMmsi", "999000002")
    invoke("expand")
    w = window()
    w.setWidth(1200)
    w.setHeight(800)
    QTest.qWait(350)
    shot("docs/demo-preview.png")
    shutil.copy("docs/demo-preview.png", "preview.png")
    radar = root.findChild(QObject, "radar")
    radar.setProperty("zoomLevel", 1)
    shot("docs/zoom-preview.png")
    from PySide6.QtCore import QPointF

    radar.setProperty("viewCenter", QPointF(-0.25, 0.25))
    shot("docs/pan-preview.png")
    radar.setProperty("zoomLevel", 0)
    radar.setProperty("viewCenter", QPointF(0, 0))
    invoke("showHelp")
    shot("docs/keyboard-preview.png")
    invoke("hideHelp")
    invoke("showSettings")
    w.setWidth(660)
    w.setHeight(800)
    QTest.qWait(150)
    shot("docs/settings-preview.png")
    print(
        "Rendered expanded, zoom, pan, keyboard and settings previews from current QML"
    )

    root.setProperty("configuring", False)
    w.setWidth(1200)
    w.setHeight(800)
    from PySide6.QtGui import QColor

    palette = top.property("previewColors")
    for prop, value in dict(
        background="#f3efdf", foreground="#263b40", accent="#846033", muted="#637775"
    ).items():
        palette.setProperty(prop, QColor(value))
    shot("docs/demo-preview-light.png")


if __name__ == "__main__":
    main()
