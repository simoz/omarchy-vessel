import QtQuick
import qs.Commons
import qs.Ui
import "."
import "Model.js" as Model

// Omarchy injects the bar and per-widget settings into this entry point.
BarWidget {
    id: root
    moduleName: "simoz.vessel"
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
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
    function revealShip(ship) {
        selectedMmsi = ship.mmsi;
        radar.focusShip(ship);
        // A list click must reveal the chart as well as the geographic contact.
        viewport.contentY = 0;
    }
    onConfiguringChanged: viewport.contentY = 0
    // Attach once per monitor while the singleton owns the shared network process.
    onSettingsChanged: if (attached) VesselService.configure(settings)
    Component.onCompleted: { attached = true; VesselService.attach(settings); }
    Component.onDestruction: if (attached) VesselService.detach()
    // Age labels need a clock only while the details panel is visible.
    Timer { interval: 1000; running: root.opened; repeat: true; onTriggered: root.now = Date.now() }

    component Label: Text {
        color: Color.foreground; font.family: root.family; font.pixelSize: 12
        textFormat: Text.PlainText
    }
    // Consistent hit-area heights and shared styling keep all panel
    // commands consistent, including the reception toggle.
    component Action: Rectangle {
        id: action
        property string text
        signal triggered()
        implicitWidth: actionLabel.implicitWidth + 16
        implicitHeight: 30
        radius: 3
        color: "transparent"
        border.width: 1
        border.color: activeFocus || pointer.containsMouse ? Color.accent : "transparent"
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: text
        Accessible.onPressAction: triggered()
        Label {
            id: actionLabel
            anchors.centerIn: parent
            text: action.text; color: Color.accent
        }
        Keys.onReturnPressed: triggered()
        Keys.onSpacePressed: triggered()
        Keys.onEscapePressed: root.close()
        MouseArea {
            id: pointer
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: action.triggered()
        }
    }

    WidgetButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: "Vessel"
        labelVisible: false
        hasVisualContent: true
        fixedWidth: root.vertical ? -1 : Style.space(16) + scaledHorizontalMargin * 2
        BoatIcon {
            anchors.centerIn: parent
            width: Style.space(16); height: width
            ink: button.foreground
        }
        tooltipText: "Vessel · " + root.report.status
        dimmed: VesselService.paused || root.report.status === "RECONNECTING" || root.report.status === "STOPPED"
        onPressed: function(b) { if (b === Qt.MiddleButton) root.refresh(); else root.toggle(); }
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
        contentHeight: fittedContentHeight(root.configuring ? form.implicitHeight : body.implicitHeight + footer.height + 12)
        PanelKeyCatcher {
            id: keys
            anchors.fill: parent
            blocked: root.configuring || radar.zoomControlsFocused || settingsAction.activeFocus || receptionAction.activeFocus || reconnectAction.activeFocus
            onCloseRequested: root.close()
            onReturnRequested: root.refresh()
            // Only the body scrolls; reception controls remain reachable on short screens.
            Flickable {
                id: viewport
                objectName: "panelViewport"
                anchors.fill: parent
                anchors.bottomMargin: root.configuring ? 0 : footer.height + 12
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
                        Label {
                            width: parent.width; wrapMode: Text.WordWrap
                            font.pixelSize: 22; font.bold: true
                            text: root.selectedShip ? (root.selectedShip.name || "MMSI " + root.selectedShip.mmsi) : ""
                        }
                        Label { text: "DESTINATION"; font.pixelSize: 9; color: Color.muted }
                        Label {
                            width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: 16
                            text: root.selectedShip ? (root.selectedShip.destination || "Not reported") : ""
                            color: root.selectedShip && root.selectedShip.destination ? Color.accent : Color.muted
                        }
                        Label {
                            width: parent.width; wrapMode: Text.WordWrap
                            text: root.selectedShip ? Model.distance(root.selectedShip.distance, root.unit) + " " + Model.compass(root.selectedShip.bearing) + " · " + Math.round(root.selectedShip.bearing) + "° from you" + "  /  " + (root.selectedShip.speed === null ? "Speed unknown" : root.selectedShip.speed.toFixed(1) + " kn") : ""
                        }
                        Label {
                            width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: 10; color: Color.muted
                            text: root.selectedShip ? root.selectedShip.type + " · MMSI " + root.selectedShip.mmsi : ""
                        }
                        Label {
                            width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: 10
                            text: root.selectedShip ? root.selectedShip.timeSource + " · " + Model.age(root.selectedShip.lastSeen, root.now) + (root.selectedShip.stale ? " · OLD POSITION" : "") : ""
                            color: root.selectedShip && root.selectedShip.stale ? Color.accent : Color.muted
                        }
                    }
                    Label {
                        width: parent.width; wrapMode: Text.WordWrap; visible: root.ships.length === 0
                        text: VesselService.paused ? "Reception paused. Press RESUME below to receive vessel positions." : root.report.status === "SETUP" ? "Your lookout is ready for setup." : "Listening for vessels. New contacts appear as AIS reports arrive."
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
                            objectName: "vessel-" + modelData.mmsi
                            width: ListView.view.width; height: 32
                            color: Color.background
                            border.width: root.selectedShip && root.selectedShip.mmsi === modelData.mmsi ? 1 : 0
                            border.color: Color.accent
                            opacity: modelData.stale ? 0.5 : 1
                            Label { anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: parent.width * 0.65; elide: Text.ElideRight; text: modelData.name || modelData.mmsi }
                            Label { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; text: Model.distance(modelData.distance, root.unit); color: Color.accent }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.revealShip(modelData) }
                        }
                    }
                    Label { width: parent.width; wrapMode: Text.WordWrap; text: root.report.demo ? "SIMULATED TRAFFIC · no live positions" : "AISStream · received vessels only · not for navigation"; font.pixelSize: 10; color: Color.muted }

                }
            }
            Item {
                id: footer
                objectName: "panelFooter"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 43
                visible: !root.configuring
                Rectangle { width: parent.width; height: 1; color: Color.muted; opacity: 0.3 }
                Row {
                    anchors.bottom: parent.bottom
                    spacing: 12
                    Action {
                        id: settingsAction
                        text: "SETTINGS"
                        onTriggered: { root.configuring = true; VesselService.loadSettings(); }
                    }
                    Action {
                        id: receptionAction
                        objectName: "pauseReception"
                        text: VesselService.paused ? "RESUME" : "PAUSE"
                        onTriggered: VesselService.togglePaused()
                    }
                    Action {
                        id: reconnectAction
                        text: "RECONNECT"
                        onTriggered: root.refresh()
                    }
                }
            }
        }
    }
}
