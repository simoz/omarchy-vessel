import QtQuick
import qs.Commons
import qs.Ui
import "."
import "Model.js" as Model

// Omarchy injects the bar and per-widget settings into this entry point.
BarWidget {
    id: root
    moduleName: "simoz.vessel"
    implicitWidth: root.vertical ? Math.max(button.implicitWidth, pauseButton.implicitWidth) : button.implicitWidth + pauseButton.implicitWidth
    implicitHeight: root.vertical ? button.implicitHeight + pauseButton.implicitHeight : Math.max(button.implicitHeight, pauseButton.implicitHeight)
    property bool configuring: false
    property bool opened: false
    property bool attached: false
    property string selectedMmsi: ""
    property double now: Date.now()
    readonly property var report: VesselService.report
    readonly property var ships: VesselService.ships
    readonly property string unit: VesselService.preferences.unit || "nm"
    // Keep selection by MMSI as distance sorting changes; fall back when a contact expires.
    readonly property var selectedShip: {
        for (var i = 0; i < ships.length; i++) if (ships[i].mmsi === selectedMmsi) return ships[i];
        return ships.length ? ships[0] : null;
    }
    readonly property string family: bar ? bar.fontFamily : "monospace"
    function open() { opened = true; }
    function close() { opened = false; configuring = false; }
    function toggle() { if (!opened && report.status === "SETUP") configuring = true; opened = !opened; }
    function refresh() { VesselService.restart(); }
    // Attach once per monitor while the singleton owns the shared network process.
    onSettingsChanged: if (attached) VesselService.configure(settings)
    Component.onCompleted: { attached = true; VesselService.attach(settings); }
    Component.onDestruction: if (attached) VesselService.detach()
    // Age labels need a clock only while the details panel is visible.
    Timer { interval: 1000; running: root.opened; repeat: true; onTriggered: root.now = Date.now() }

    WidgetButton {
        id: button
        anchors.left: parent.left
        anchors.top: parent.top
        width: root.vertical ? root.width : root.width - pauseButton.width
        height: root.vertical ? root.height - pauseButton.height : root.height
        bar: root.bar
        text: (root.report.demo ? "DEMO " : "") + root.ships.length + (root.ships.length ? " · " + Model.distance(root.ships[0].distance, root.unit) : "")
        labelVisible: false
        hasVisualContent: true
        fixedWidth: root.vertical ? -1 : boatLabel.implicitWidth + scaledHorizontalMargin * 2
        Row {
            id: boatLabel
            anchors.centerIn: parent
            spacing: 6
            BoatIcon { width: Style.space(16); height: width; ink: button.foreground; anchors.verticalCenter: parent.verticalCenter }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                visible: !root.vertical
                text: button.text; color: button.foreground
                font.family: button.fontFamily; font.pixelSize: button.fontSize
            }
        }
        tooltipText: "Vessel · " + root.report.status
        dimmed: VesselService.paused || root.report.status === "RECONNECTING" || root.report.status === "STOPPED"
        onPressed: function(b) { if (b === Qt.MiddleButton) root.refresh(); else root.toggle(); }
    }
    ReceptionButton {
        id: pauseButton
        objectName: "pauseReception"
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        width: root.vertical ? root.width : implicitWidth
        height: root.vertical ? implicitHeight : root.height
        bar: root.bar
    }
    // Use the host panel for anchoring, focus and outside-click dismissal.
    KeyboardPanel {
        id: panel
        anchorItem: button
        owner: root
        bar: root.bar
        open: root.opened
        focusTarget: keys
        contentWidth: fittedContentWidth(Style.space(440))
        contentHeight: fittedContentHeight(root.configuring ? form.implicitHeight : body.implicitHeight)
        PanelKeyCatcher {
            id: keys
            anchors.fill: parent
            blocked: root.configuring || radar.zoomControlsFocused
            onCloseRequested: root.close()
            onReturnRequested: root.refresh()
            // Allow the whole panel to scroll when the available screen height is limited.
            Flickable {
                anchors.fill: parent
                contentHeight: root.configuring ? form.implicitHeight : body.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                SettingsForm {
                    id: form
                    width: parent.width
                    family: root.family
                    visible: root.configuring
                    onDone: root.configuring = false
                    Keys.onEscapePressed: root.configuring = false
                }
                Column {
                    id: body
                    visible: !root.configuring
                    width: parent.width
                    spacing: 12
                    component Label: Text {
                        color: Color.foreground; font.family: root.family; font.pixelSize: 12
                        textFormat: Text.PlainText
                    }
                    Row {
                        width: parent.width
                        Label { width: parent.width * 0.6; text: "V E S S E L  /  MARINE RADAR"; color: Color.accent; font.bold: true; font.pixelSize: 11 }
                        Label { width: parent.width * 0.4; text: VesselService.paused ? "PAUSED" : root.report.status; color: Color.muted; horizontalAlignment: Text.AlignRight }
                    }
                    Rectangle { width: parent.width; height: 1; color: Color.accent; opacity: 0.4 }
                    Label {
                        width: parent.width; wrapMode: Text.WordWrap
                        text: root.report.location || "Finding your lookout…"
                        color: Color.muted
                    }
                    Item {
                        width: parent.width
                        height: Math.min(width, 340)
                        Radar {
                            id: radar
                            objectName: "radar"
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: parent.height; height: width
                            scanning: root.opened && !root.configuring && !VesselService.paused
                            ships: root.ships; radiusNm: root.report.radius || 25
                            basemap: VesselService.basemap
                            selectedMmsi: root.selectedShip ? root.selectedShip.mmsi : ""
                            onCloseRequested: root.close()
                            onSelected: function(mmsi) { root.selectedMmsi = mmsi; }
                        }
                        Robot { width: 48; height: 48; anchors.right: parent.right; anchors.bottom: parent.bottom; awake: !VesselService.paused && (root.report.status === "LIVE" || root.report.demo === true); visible: root.opened }
                    }
                    Row {
                        width: parent.width
                        Label { width: parent.width / 2; text: "VIEW / " + Model.distance(radar.viewRadiusNm, root.unit); color: Color.muted }
                        Label { width: parent.width / 2; text: radar.visibleShips.length + " / " + (root.report.total || 0) + " CONTACTS"; horizontalAlignment: Text.AlignRight; color: Color.accent }
                    }
                    Label {
                        text: VesselService.basemap.available ? "NATURAL EARTH · CITIES © GEONAMES" : "BASEMAP UNAVAILABLE"
                        font.pixelSize: 9; color: Color.muted
                    }
                    Rectangle { width: parent.width; height: 1; color: Color.muted; opacity: 0.3 }
                    Column {
                        width: parent.width; spacing: 6; visible: root.selectedShip !== null
                        Label { width: parent.width; elide: Text.ElideRight; font.pixelSize: 20; text: root.selectedShip ? (root.selectedShip.name || "MMSI " + root.selectedShip.mmsi) : "" }
                        Label { text: root.selectedShip ? root.selectedShip.type + " · " + root.selectedShip.mmsi : ""; color: Color.muted }
                        Label {
                            width: parent.width; wrapMode: Text.WordWrap
                            text: root.selectedShip ? Model.distance(root.selectedShip.distance, root.unit) + " " + Model.compass(root.selectedShip.bearing) + " · " + Math.round(root.selectedShip.bearing) + "° from you" + "  /  " + (root.selectedShip.speed === null ? "Speed unknown" : root.selectedShip.speed.toFixed(1) + " kn") : ""
                        }
                        Label { width: parent.width; wrapMode: Text.WordWrap; text: root.selectedShip ? "DEST / " + (root.selectedShip.destination || "Not reported") : ""; color: Color.muted }
                        Label { text: root.selectedShip ? root.selectedShip.timeSource + " · " + Model.age(root.selectedShip.lastSeen, root.now) + (root.selectedShip.stale ? " · OLD POSITION" : "") : ""; color: root.selectedShip && root.selectedShip.stale ? Color.accent : Color.muted }
                    }
                    Label {
                        width: parent.width; wrapMode: Text.WordWrap; visible: root.ships.length === 0
                        text: VesselService.paused ? "Reception paused. Resume from the bar to receive vessel positions." : root.report.status === "SETUP" ? "Your lookout is ready for setup." : "Listening for vessels. New contacts appear as AIS reports arrive."
                        color: Color.muted
                    }
                    Label {
                        width: parent.width; wrapMode: Text.WordWrap; visible: !!root.report.error
                        text: root.report.error || ""; color: Color.accent
                    }
                    // Bound the contact list height; the receiver already sorts by distance.
                    ListView {
                        width: parent.width
                        height: Math.min(contentHeight, 144)
                        clip: true
                        model: root.ships
                        spacing: 4
                        delegate: Rectangle {
                            required property var modelData
                            width: ListView.view.width; height: 32
                            color: Color.background
                            border.width: root.selectedShip && root.selectedShip.mmsi === modelData.mmsi ? 1 : 0
                            border.color: Color.accent
                            opacity: modelData.stale ? 0.5 : 1
                            Label { anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: parent.width * 0.65; elide: Text.ElideRight; text: modelData.name || modelData.mmsi }
                            Label { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; text: Model.distance(modelData.distance, root.unit); color: Color.accent }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.selectedMmsi = modelData.mmsi }
                        }
                    }
                    Label { width: parent.width; wrapMode: Text.WordWrap; text: root.report.demo ? "SIMULATED TRAFFIC · no live positions" : "AISStream · received vessels only · not for navigation"; font.pixelSize: 10; color: Color.muted }
                    Row {
                        spacing: 24
                        Label {
                            text: "SETTINGS"; color: Color.accent
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { root.configuring = true; VesselService.loadSettings(); } }
                        }
                        Label {
                            text: "RECONNECT ↵"; color: Color.accent
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.refresh() }
                        }
                    }
                }
            }
        }
    }
}
