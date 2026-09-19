#!/usr/bin/env python3
"""Render detailed-map previews from a real Genoa AIS capture.

Requires PySide6, VESSEL_PREVIEW_LIVE (receiver snapshot JSON) and
VESSEL_PREVIEW_DETAIL (map batch JSON, Genoa / 25 nm / zoom 8 / center 0,0).
The renderer uses local input only; it never connects or uses credentials.
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
        "DetailMap.qml",
        "OfflineMap.qml",
        "RadarLabels.qml",
        "Robot.qml",
        "Model.js",
        "ShipModel.qml",
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
        'import QtQuick\nItem {property var bar; property string text; property bool labelVisible; property bool hasVisualContent; property real fixedWidth; property real fixedHeight; property real scaledHorizontalMargin:4; property real scaledVerticalPadding:6; property color foreground:"white"; property string tooltipText; property bool dimmed; signal pressed(int b); implicitWidth:28; implicitHeight:28}',
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
    from pathlib import Path

    from PySide6.QtCore import QMetaObject, QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest

    sys.path.insert(0, str(Path.cwd() / "backend"))
    import basemap
    from geometry import GENOA

    base = root
    import shutil

    shutil.copy("Widget.qml", base / "Widget.qml")
    report = json.loads(Path(os.environ["VESSEL_PREVIEW_LIVE"]).read_text())
    assert report.get("ships") and report.get("provider") in ("openwaters", "aisstream")
    assert [report.get("latitude"), report.get("longitude"), report.get("radius")] == [
        *GENOA,
        25,
    ]
    detail = json.loads(Path(os.environ["VESSEL_PREVIEW_DETAIL"]).read_text())
    assert detail.get("available") and detail.get("origin") == [*GENOA, 25]
    assert detail["x"] == 0 and detail["y"] == 0
    geo = basemap.build(*GENOA, 25)
    service = """pragma Singleton
    import QtQuick
    Item {
     property var report: REPORT
     property var ships: report.ships
     property var basemap: MAP
     property var preferences: ({provider:"openwaters",hasOpenwatersKey:false,unit:"nm",radiusNm:25,cityName:"Genoa",latitude:44.4056,longitude:8.9463,autoLocation:false,hasApiKey:false})
     property var mapDetail: ({available:false})
     property string completedDetail: ""
     property double detailRetryAt: 0
     function requestDetail(query) {}
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

    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor

    root.setProperty("selectedMmsi", report["ships"][0]["mmsi"])
    invoke("expand")
    w = window()
    w.setWidth(1200)
    w.setHeight(800)
    radar = root.findChild(QObject, "radar")
    radar.setProperty("detail", detail)
    radar.setProperty("zoomLevel", 3)
    radar.setProperty("viewCenter", QPointF(0, 0))
    assert radar.property("detailed")
    shot("docs/live-detail-preview.png")
    palette = top.property("previewColors")
    for prop, value in dict(
        background="#f3efdf", foreground="#263b40", accent="#846033", muted="#637775"
    ).items():
        palette.setProperty(prop, QColor(value))
    shot("docs/live-detail-preview-light.png")
    shutil.copy("docs/live-detail-preview-light.png", "preview.png")
    print("Rendered dark and light detailed-map previews from real AIS data")


if __name__ == "__main__":
    main()
