import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic as Controls
import Quickshell
import qs.Commons
import qs.Ui
import "."
import "Model.js" as Model
import "Keyboard.js" as Keyboard

// Omarchy injects the bar and per-widget settings into this entry point.
BarWidget {
    id: root
    moduleName: "simoz.vessel"
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    property bool configuring: false
    property bool helpOpen: false
    property var helpPreviousFocus: null
    property bool opened: false
    property bool expanded: false
    readonly property bool viewing: opened || expanded
    property bool attached: false
    property string selectedMmsi: ""
    property double now: Date.now()
    readonly property int textSize: expanded ? 15 : 14
    readonly property int smallTextSize: expanded ? 12 : 11
    readonly property var report: VesselService.report
    readonly property var ships: VesselService.ships
    readonly property string unit: VesselService.preferences.unit || "nm"
    // Keep selection by MMSI as distance sorting changes; fall back when a contact expires.
    readonly property var selectedShip: {
        for (var i = 0; i < ships.length; i++) if (ships[i].mmsi === selectedMmsi) return ships[i];
        return ships.length ? ships[0] : null;
    }
    readonly property string family: bar ? bar.fontFamily : "monospace"
    // The panel and expanded window share one scene. Change its parent rather
    // than recreate it, so zoom, selection and unsaved form fields survive.
    function focusCurrentView() {
        if (root.configuring)
            form.focusFirst();
        else
            radar.forceActiveFocus();
    }
    function open() {
        if (!expanded)
            opened = true;
    }
    function close() {
        helpOpen = false;
        opened = false;
        expanded = false;
        configuring = false;
    }
    function expand() {
        expanded = true;
        opened = false;
        Qt.callLater(root.focusCurrentView);
    }
    function collapse() {
        opened = true;
        expanded = false;
        Qt.callLater(root.focusCurrentView);
    }
    function toggle() {
        if (expanded) {
            collapse();
            return;
        }
        if (!opened && report.status === "SETUP")
            configuring = true;
        opened = !opened;
    }
    function refresh() { VesselService.restart(); }
    function revealShip(ship) {
        selectedMmsi = ship.mmsi;
        radar.focusShip(ship);
        // A list click must reveal the chart as well as the geographic contact.
        viewport.contentY = 0;
    }
    function showHelp() {
        helpPreviousFocus = keys.Window.window ? keys.Window.window.activeFocusItem : null;
        helpOpen = true;
        help.forceActiveFocus();
    }
    function hideHelp() {
        helpOpen = false;
        if (helpPreviousFocus && helpPreviousFocus.visible && helpPreviousFocus.enabled) helpPreviousFocus.forceActiveFocus();
        else keys.forceActiveFocus();
    }
    function showSettings() {
        configuring = true;
        VesselService.loadSettings();
        Qt.callLater(() => form.focusFirst());
    }
    function selectVessel(step) {
        if (!ships.length) return;
        var index = ships.findIndex(ship => ship.mmsi === (selectedShip ? selectedShip.mmsi : ""));
        index = (Math.max(0, index) + step + ships.length) % ships.length;
        revealShip(ships[index]);
        contacts.positionViewAtIndex(index, ListView.Contain);
    }
    // Keyboard focus can move below the fold; scroll only as far as necessary.
    function ensureVisible(item) {
        var point = item.mapToItem(viewport.contentItem, 0, 0);
        var target = viewport.contentY;
        if (point.y < target) target = point.y;
        else if (point.y + item.height > target + viewport.height) target = point.y + item.height - viewport.height;
        viewport.contentY = Math.max(0, Math.min(target, Math.max(0, viewport.contentHeight - viewport.height)));
    }
    // Mouse controls and keyboard shortcuts call the same view/service actions.
    function runCommand(command) {
        switch (command) {
        case "help": showHelp(); break;
        case "dismiss": close(); break;
        case "left": radar.pan(-1, 0); break;
        case "right": radar.pan(1, 0); break;
        case "up": radar.pan(0, -1); break;
        case "down": radar.pan(0, 1); break;
        case "zoomIn": radar.zoomIn(); break;
        case "zoomOut": radar.zoomOut(); break;
        case "center": radar.recenter(); break;
        case "previous": selectVessel(-1); break;
        case "next": selectVessel(1); break;
        case "pause": VesselService.togglePaused(); break;
        case "reconnect": refresh(); break;
        case "settings": showSettings(); break;
        case "expand": expanded ? collapse() : expand(); break;
        case "pageUp": viewport.contentY = Math.max(0, viewport.contentY - viewport.height * 0.8); break;
        case "pageDown": viewport.contentY = Math.min(Math.max(0, viewport.contentHeight - viewport.height), viewport.contentY + viewport.height * 0.8); break;
        }
    }
    onConfiguringChanged: {
        viewport.contentY = 0;
        Qt.callLater(() => configuring ? form.focusFirst() : keys.forceActiveFocus());
    }
    // Attach once per monitor while the singleton owns the shared network process.
    onSettingsChanged: if (attached) VesselService.configure(settings)
    onViewingChanged: if (attached) VesselService.setViewing(viewing)
    Component.onCompleted: {
        VesselService.attach(settings);
        attached = true;
        if (viewing) VesselService.setViewing(true);
    }
    Component.onDestruction: {
        if (attached) {
            if (viewing) VesselService.setViewing(false);
            VesselService.detach();
        }
    }
    // Age labels need a clock only while the details panel is visible.
    Timer { interval: 1000; running: root.viewing; repeat: true; onTriggered: root.now = Date.now() }

    component Label: Text {
        color: Color.foreground; font.family: root.family; font.pixelSize: root.textSize
        textFormat: Text.PlainText
    }
    // Consistent hit-area heights and shared styling keep all panel
    // commands consistent, including the reception toggle.
    component Action: Rectangle {
        id: action
        property string text
        property bool iconOnly: false
        property bool checkable: false
        property bool checked: false
        property bool hoverOnly: false
        property bool hovered: false
        signal triggered()
        implicitWidth: actionLabel.implicitWidth + 16
        implicitHeight: 30
        radius: 3
        color: checked && !hoverOnly ? Qt.alpha(Color.accent, 0.15) : "transparent"
        border.width: 1
        // Expansion keeps its accessible state without a persistent visual selection.
        border.color: hoverOnly ? (hovered ? Color.accent : "transparent")
            : checked ? Color.accent : activeFocus ? Color.foreground
            : hovered ? Color.muted : "transparent"
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: text
        Accessible.checkable: checkable
        Accessible.checked: checked
        Accessible.onPressAction: triggered()
        Label {
            id: actionLabel
            anchors.centerIn: parent
            visible: !action.iconOnly
            text: action.text; color: Color.accent
        }
        Keys.onReturnPressed: triggered()
        Keys.onEnterPressed: triggered()
        Keys.onSpacePressed: triggered()
        Keys.onEscapePressed: root.configuring ? form.cancel() : root.close()
        MouseArea {
            id: pointer
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onEntered: action.hovered = true
            onExited: action.hovered = false
            onPositionChanged: action.hovered = containsMouse
            onClicked: {
                // Moving the control to another window may not emit an exit event.
                action.hovered = false;
                action.triggered();
            }
        }
    }

    WidgetButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        // Size the slot from the actual icon, not a hidden font glyph whose
        // advance can vary between the user's fonts and fallback fonts.
        fixedWidth: root.vertical ? -1 : boatIcon.width + scaledHorizontalMargin * 2
        fixedHeight: root.vertical ? boatIcon.height + scaledVerticalPadding * 2 : -1
        labelVisible: false
        hasVisualContent: true
        BoatIcon {
            id: boatIcon
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
        contentHeight: fittedContentHeight((root.configuring ? form.implicitHeight : body.implicitHeight) + footer.height + 12)
        Item { id: panelSlot; anchors.fill: parent }
    }
    FloatingWindow {
        id: expandedWindow
        title: "Vessel · Marine radar"
        visible: root.expanded
        implicitWidth: 1100
        implicitHeight: 760
        minimumSize: Qt.size(440, 420)
        color: Color.background
        onVisibleChanged: if (!visible && root.expanded) root.close()
        Item { id: windowSlot; anchors.fill: parent; anchors.margins: 20 }
    }
    // Move the existing scene between surfaces to preserve map and form state.
    FocusScope {
        id: keys
        parent: root.expanded ? windowSlot : panelSlot
        readonly property bool wide: root.expanded && width >= 760
        anchors.fill: parent
        focus: true
        // Descendants get activation and editing keys first; native Tab traversal
        // stays intact instead of being swallowed by the host key dispatcher.
        Keys.priority: Keys.AfterItem
        Keys.onPressed: function(event) {
            if (!root.viewing || root.helpOpen || root.configuring) return;
            var command = Keyboard.command(event.key, event.text, event.modifiers);
            if (!command) return;
            event.accepted = true;
            if (event.isAutoRepeat && ["help", "pause", "expand", "settings", "reconnect", "dismiss"].indexOf(command) !== -1) return;
            root.runCommand(command);
        }
        // Only the body scrolls; reception controls remain reachable on short screens.
        Flickable {
            id: viewport
            enabled: !root.helpOpen
            objectName: "panelViewport"
            anchors.fill: parent
            anchors.bottomMargin: footer.height + 12
            contentHeight: root.configuring ? form.implicitHeight : body.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            SettingsForm {
                id: form
                width: parent.width
                family: root.family
                visible: root.configuring
                onFocusRequested: function(item) { root.ensureVisible(item); }
                onDone: root.configuring = false
                Keys.onEscapePressed: root.configuring = false
            }
            Column {
                id: body
                visible: !root.configuring
                width: parent.width
                spacing: 12
                Item {
                    width: parent.width; height: 30
                    Label {
                        anchors.left: parent.left; anchors.right: headerActions.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: "VESSEL / MARINE RADAR"; elide: Text.ElideRight
                        color: Color.accent; font.bold: true; font.pixelSize: root.smallTextSize + 1
                    }
                    Row {
                        id: headerActions
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        spacing: 4
                        Action {
                            id: expandAction
                            objectName: "expandView"
                            text: "Expanded view (F)"
                            checkable: true
                            checked: root.expanded
                            hoverOnly: true
                            implicitWidth: 30; implicitHeight: 30
                            iconOnly: true
                            onTriggered: root.expanded ? root.collapse() : root.expand()
                            // A stable, two-headed diagonal arrow identifies the toggle.
                            Canvas {
                                anchors.centerIn: parent
                                width: 18; height: 18
                                property color ink: Color.accent
                                onInkChanged: requestPaint()
                                onPaint: {
                                    var c = getContext("2d"); c.reset();
                                    c.strokeStyle = ink; c.lineWidth = 1.5;
                                    c.lineCap = "round"; c.lineJoin = "round";
                                    c.beginPath();
                                    c.moveTo(3, 15); c.lineTo(15, 3);
                                    c.moveTo(3, 9); c.lineTo(3, 15); c.lineTo(9, 15);
                                    c.moveTo(9, 3); c.lineTo(15, 3); c.lineTo(15, 9);
                                    c.stroke();
                                }
                            }
                        }
                        Action {
                            id: helpAction
                            objectName: "keyboardHelp"
                            text: "Keyboard shortcuts (?)"
                            implicitWidth: 30; implicitHeight: 30
                            iconOnly: true
                            onTriggered: root.showHelp()
                            KeyboardIcon { anchors.centerIn: parent; ink: Color.accent }
                        }
                    }
                }
                Item {
                    width: parent.width; height: Math.max(locationLabel.implicitHeight, statusBadge.implicitHeight)
                    Label {
                        id: locationLabel
                        anchors.left: parent.left; anchors.right: statusBadge.left; anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.report.location || "Finding your lookout…"
                        elide: Text.ElideRight; color: Color.muted
                    }
                    Action {
                        id: statusBadge
                        objectName: "pauseReception"
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        implicitWidth: statusContent.implicitWidth + 16
                        implicitHeight: 28
                        iconOnly: true
                        checkable: true
                        checked: !VesselService.paused
                        text: VesselService.paused ? "Resume reception (P)" : "Pause reception (P)"
                        color: "transparent"
                        border.color: activeFocus ? Color.foreground : hovered ? Color.muted : "transparent"
                        onTriggered: VesselService.togglePaused()
                        Controls.ToolTip.visible: hovered
                        Controls.ToolTip.delay: 500
                        Controls.ToolTip.text: text
                        readonly property bool live: !VesselService.paused && root.report.status === "LIVE"
                        Row {
                            id: statusContent
                            anchors.centerIn: parent
                            spacing: 6
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: 6; height: 6; radius: 3
                                color: statusBadge.live ? Color.accent : Color.muted
                            }
                            Label {
                                text: VesselService.paused ? "PAUSED" : root.report.status
                                color: statusBadge.live ? Color.accent : Color.muted
                                font.bold: true; font.pixelSize: root.smallTextSize + 1
                            }
                        }
                    }
                }
                Rectangle { width: parent.width; height: 1; color: Color.accent; opacity: 0.4 }
                // The chart and vessel details share a row only when both fit.
                Grid {
                    width: parent.width
                    columns: keys.wide ? 2 : 1
                    spacing: 20
                    Column {
                        width: keys.wide ? parent.width - 340 : parent.width
                        spacing: 12
                        Item {
                            width: parent.width
                            height: root.expanded ? Math.min(width, Math.max(300, keys.height - 260)) : Math.min(width, 380)
                            Radar {
                                id: radar
                                objectName: "radar"
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: parent.height; height: width
                                controlsRightMargin: (width - parent.width) / 2
                                scanning: root.viewing && !root.configuring && !VesselService.paused
                                markerSize: root.expanded ? 14 : 12
                                ships: root.ships; radiusNm: root.report.radius || 25
                                basemap: VesselService.basemap
                                // Source changes update geography without owning camera state.
                                detail: VesselService.mapDetail
                                failedDetailQuery: VesselService.completedDetail && isFinite(VesselService.detailRetryAt)
                                    ? VesselService.completedDetail : ""
                                detailEnabled: root.viewing && !root.configuring
                                onDetailRequested: query => VesselService.requestDetail(query)
                                selectedMmsi: root.selectedShip ? root.selectedShip.mmsi : ""
                                onCloseRequested: root.close()
                                onSelected: function(mmsi) { root.selectedMmsi = mmsi; }
                            }
                            Robot {
                                objectName: "lookoutRobot"
                                width: 48; height: 48
                                anchors.right: parent.right; anchors.bottom: parent.bottom
                                awake: !VesselService.paused && ["LIVE", "LISTENING"].indexOf(root.report.status) !== -1
                                live: !VesselService.paused && root.report.status === "LIVE"
                                visible: root.viewing
                            }
                        }
                        Row {
                            width: parent.width
                            Label { width: parent.width / 2; text: "VIEW / " + Model.distance(radar.viewRadiusNm, root.unit); color: Color.muted }
                            Label { width: parent.width / 2; text: radar.visibleShips.length + " / " + (root.report.total || 0) + " CONTACTS"; horizontalAlignment: Text.AlignRight; color: Color.accent }
                        }
                        Text {
                            width: parent.width
                            visible: radar.detailed
                            text: '<a href="https://openfreemap.org/">OpenFreeMap</a> · <a href="https://openmaptiles.org/">© OpenMapTiles</a> · <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap</a>'
                            textFormat: Text.StyledText
                            font.pixelSize: root.smallTextSize
                            font.family: root.family
                            color: Color.muted; linkColor: Color.muted
                            wrapMode: Text.Wrap
                            onLinkActivated: link => Qt.openUrlExternally(link)
                        }
                        Label {
                            visible: !radar.detailed
                            text: radar.mapLoading ? "LOADING MAP…" : (VesselService.basemap.available ? "OFFLINE MAP · NATURAL EARTH · © GEONAMES" : "BASEMAP UNAVAILABLE")
                            font.pixelSize: root.smallTextSize; color: Color.muted
                        }
                        Label {
                            width: parent.width; wrapMode: Text.WordWrap
                            text: "● STATIONARY · ▲ MOVING · ○ SPEED UNKNOWN"
                            font.pixelSize: root.smallTextSize; color: Color.muted
                        }
                    }
                    Column {
                        width: keys.wide ? 320 : parent.width
                        spacing: 12
                        Rectangle { visible: !keys.wide; width: parent.width; height: 1; color: Color.muted; opacity: 0.3 }
                        Column {
                            width: parent.width; spacing: 14; visible: root.selectedShip !== null
                            Column {
                                width: parent.width; spacing: 3
                                Item {
                                    width: parent.width
                                    height: Math.max(vesselName.implicitHeight, vesselLink.height)
                                    Label {
                                        id: vesselName
                                        width: Math.min(implicitWidth, parent.width - vesselLink.width - 8)
                                        wrapMode: Text.WordWrap
                                        font.pixelSize: 22; font.bold: true
                                        text: root.selectedShip ? (root.selectedShip.name || "Unnamed vessel") : ""
                                    }
                                    Action {
                                        id: vesselLink
                                        objectName: "openVesselPage"
                                        anchors.left: vesselName.right; anchors.leftMargin: 8
                                        anchors.top: parent.top
                                        readonly property string vesselUrl: Model.vesselUrl(root.selectedShip)
                                        readonly property bool hasImo: !!root.selectedShip && /^[1-9][0-9]{6}$/.test(String(root.selectedShip.imo))
                                        text: hasImo ? "Open vessel details on VesselFinder" : "Search vessel by MMSI on VesselFinder"
                                        implicitWidth: 30; implicitHeight: 30
                                        iconOnly: true
                                        color: "transparent"
                                        border.color: activeFocus ? Color.accent : "transparent"
                                        enabled: vesselUrl.length > 0
                                        onTriggered: if (enabled) Qt.openUrlExternally(vesselUrl)
                                        onActiveFocusChanged: if (activeFocus) root.ensureVisible(vesselLink)
                                        Controls.ToolTip.visible: hovered
                                        Controls.ToolTip.delay: 500
                                        Controls.ToolTip.text: text
                                        Label {
                                            anchors.centerIn: parent
                                            text: "↗"; font.pixelSize: 22; color: Color.accent
                                        }
                                    }
                                }
                                Label {
                                    width: parent.width; wrapMode: Text.WordWrap
                                    font.pixelSize: root.smallTextSize; color: Color.muted
                                    text: root.selectedShip ? root.selectedShip.type : ""
                                }
                            }
                            Row {
                                width: parent.width; spacing: 8
                                Repeater {
                                    model: [
                                        {label: "DISTANCE", value: root.selectedShip ? Model.distance(root.selectedShip.distance, root.unit) : "—"},
                                        {label: "BEARING", value: root.selectedShip ? Model.compass(root.selectedShip.bearing) + " " + Math.round(root.selectedShip.bearing) + "°" : "—"},
                                        {label: "SPEED", value: root.selectedShip && root.selectedShip.speed !== null ? root.selectedShip.speed.toFixed(1) + " kn" : "—"}
                                    ]
                                    Column {
                                        required property var modelData
                                        width: (parent.width - 16) / 3; spacing: 4
                                        Label {
                                            text: modelData.label
                                            font.pixelSize: root.smallTextSize; color: Color.muted
                                        }
                                        Label {
                                            width: parent.width; wrapMode: Text.WordWrap
                                            text: modelData.value
                                            font.bold: true
                                        }
                                    }
                                }
                            }
                            Row {
                                width: parent.width; spacing: 8
                                Column {
                                    readonly property string destination: root.selectedShip ? (root.selectedShip.destination || "").trim() : ""
                                    width: (parent.width - 16) / 3
                                    spacing: 4
                                    Label { text: "DESTINATION"; font.pixelSize: root.smallTextSize; color: Color.muted }
                                    Label { width: parent.width; wrapMode: Text.Wrap; text: parent.destination || "—" }
                                }
                                Column {
                                    id: mmsiField
                                    width: (parent.width - 16) / 3; spacing: 4
                                    Label { id: mmsiCaption; text: "MMSI"; font.pixelSize: root.smallTextSize; color: Color.muted }
                                    Label { id: mmsiValue; text: root.selectedShip ? root.selectedShip.mmsi : "—" }
                                }
                                Column {
                                    id: imoField
                                    width: (parent.width - 16) / 3; spacing: 4
                                    Label { id: imoCaption; text: "IMO"; font.pixelSize: root.smallTextSize; color: Color.muted }
                                    Label { id: imoValue; text: vesselLink.hasImo ? String(root.selectedShip.imo) : "—" }
                                }
                            }
                            Rectangle { width: parent.width; height: 1; color: Color.muted; opacity: 0.2 }
                            Column {
                                width: parent.width; spacing: 3
                                Label {
                                    width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: root.smallTextSize
                                    text: root.selectedShip ? root.selectedShip.timeSource + " · " + Model.age(root.selectedShip.lastSeen, root.now) + (root.selectedShip.stale ? " · OLD POSITION" : "") : ""
                                    color: root.selectedShip && root.selectedShip.stale ? Color.accent : Color.muted
                                }
                                Label {
                                    width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: root.smallTextSize; color: Color.muted
                                    text: root.selectedShip ? (root.selectedShip.attribution || "") : ""
                                    visible: text.length > 0
                                }
                            }
                            Rectangle { width: parent.width; height: 1; color: Color.muted; opacity: 0.2 }
                        }
                        Label {
                            width: parent.width; wrapMode: Text.WordWrap; visible: root.ships.length === 0
                            text: VesselService.paused ? "Reception paused. Click PAUSED next to the location, or press P, to resume." : root.report.status === "SETUP" ? "Your lookout is ready for setup." : "Listening for vessels. New contacts appear as AIS reports arrive."
                            color: Color.muted
                        }
                        Label {
                            width: parent.width; wrapMode: Text.WordWrap; visible: !!root.report.error
                            text: root.report.error || ""; color: Color.accent
                        }
                        ShipModel { id: contactModel; ships: root.ships }
                        // Bound the contact list height; the receiver already sorts by distance.
                        ListView {
                            id: contacts
                            objectName: "contacts"
                            activeFocusOnTab: true
                            Accessible.role: Accessible.List
                            Accessible.name: "Vessels; use Up and Down to select"
                            onActiveFocusChanged: if (activeFocus) root.ensureVisible(contacts)
                            Keys.onUpPressed: root.selectVessel(-1)
                            Keys.onDownPressed: root.selectVessel(1)
                            Keys.onReturnPressed: if (root.selectedShip) root.revealShip(root.selectedShip)
                            Keys.onEnterPressed: if (root.selectedShip) root.revealShip(root.selectedShip)
                            Keys.onSpacePressed: if (root.selectedShip) root.revealShip(root.selectedShip)
                            Rectangle { anchors.fill: parent; color: "transparent"; border.color: Color.accent; visible: contacts.activeFocus; z: 2 }
                            width: parent.width
                            height: Math.min(contentHeight, keys.wide ? Math.max(144, keys.height - 380) : 144)
                            clip: true
                            model: contactModel
                            spacing: 4
                            delegate: Rectangle {
                                required property var ship
                                readonly property var modelData: ship
                                objectName: "vessel-" + modelData.mmsi
                                width: ListView.view.width; height: 38
                                color: Color.background
                                border.width: root.selectedShip && root.selectedShip.mmsi === modelData.mmsi ? 1 : 0
                                border.color: Color.accent
                                opacity: modelData.stale ? 0.5 : 1
                                Label { anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: parent.width * 0.65; elide: Text.ElideRight; text: modelData.name || modelData.mmsi }
                                Label { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; text: Model.distance(modelData.distance, root.unit); color: Color.accent }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.revealShip(modelData) }
                            }
                        }
                        Label { width: parent.width; wrapMode: Text.WordWrap; text: (root.report.provider === "aisstream" ? "AISStream" : "OpenWaters") + " · received vessels only · not for navigation"; font.pixelSize: root.smallTextSize; color: Color.muted }
                    }
                }
            }
        }
        Item {
            id: footer
            enabled: !root.helpOpen
            objectName: "panelFooter"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 43
            Rectangle { width: parent.width; height: 1; color: Color.muted; opacity: 0.3 }
            Row {
                anchors.bottom: parent.bottom
                spacing: 4
                visible: !root.configuring
                Action {
                    id: settingsAction
                    text: "SETTINGS"
                    onTriggered: root.showSettings()
                }
            }
            Row {
                anchors.bottom: parent.bottom
                spacing: 12
                visible: root.configuring
                Action {
                    objectName: "saveSettings"
                    text: VesselService.saving ? "SAVING…" : "SAVE & CONNECT"
                    enabled: form.canSave
                    opacity: enabled ? 1 : 0.4
                    onTriggered: form.save()
                }
                Action {
                    text: "CANCEL"
                    enabled: !VesselService.saving
                    onTriggered: form.cancel()
                }
            }
        }
        KeyboardHelp {
            id: help
            objectName: "keyboardHelpSheet"
            anchors.fill: parent
            z: 10
            visible: root.helpOpen
            centered: root.expanded
            family: root.family
            onClosed: root.hideHelp()
        }
    }
}
