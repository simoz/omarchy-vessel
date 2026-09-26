import QtQuick
import QtQuick.Controls.Basic as Controls
import qs.Commons
import "Model.js" as Model

// Details of the selected vessel. The widget supplies the selection, units and
// clock; missing AIS values show "—".
Column {
    id: root
    property var ship: null
    property string unit: "nm"
    property double now: Date.now()
    property string family: "monospace"
    property int textSize: 14
    property int smallTextSize: 11
    signal focusRequested(var item)
    signal closeRequested()
    spacing: 14
    visible: ship !== null

    component Label: Text {
        color: Color.foreground; font.family: root.family; font.pixelSize: root.textSize
        textFormat: Text.PlainText
    }
    // Three equal columns of caption and value.
    component DetailRow: Row {
        id: detailRow
        property var fields: []
        property bool bold: false
        spacing: 8
        Repeater {
            model: detailRow.fields
            Column {
                required property var modelData
                width: (parent.width - 16) / 3; spacing: 4
                Label {
                    text: modelData.label
                    font.pixelSize: root.smallTextSize; color: Color.muted
                }
                Label {
                    // Wrap breaks long unspaced values, such as port codes, when needed.
                    width: parent.width; wrapMode: Text.Wrap
                    text: modelData.value || "—"
                    font.bold: detailRow.bold
                }
            }
        }
    }

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
                text: root.ship ? (root.ship.name || "Unnamed vessel") : ""
            }
            Rectangle {
                id: vesselLink
                objectName: "openVesselPage"
                anchors.left: vesselName.right; anchors.leftMargin: 8
                anchors.top: parent.top
                readonly property string vesselUrl: Model.vesselUrl(root.ship)
                readonly property bool hasImo: !!root.ship && /^[1-9][0-9]{6}$/.test(String(root.ship.imo))
                readonly property string text: hasImo ? "Open vessel details on VesselFinder" : "Search vessel by MMSI on VesselFinder"
                function open() { if (enabled) Qt.openUrlExternally(vesselUrl); }
                width: 30; height: 30; radius: 3
                color: "transparent"
                border.width: 1
                border.color: activeFocus ? Color.accent : "transparent"
                enabled: vesselUrl.length > 0
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: text
                Accessible.onPressAction: open()
                onActiveFocusChanged: if (activeFocus) root.focusRequested(vesselLink)
                Keys.onReturnPressed: open()
                Keys.onEnterPressed: open()
                Keys.onSpacePressed: open()
                Keys.onEscapePressed: root.closeRequested()
                Controls.ToolTip.visible: pointer.containsMouse
                Controls.ToolTip.delay: 500
                Controls.ToolTip.text: text
                Label {
                    anchors.centerIn: parent
                    text: "↗"; font.pixelSize: 22; color: Color.accent
                }
                MouseArea {
                    id: pointer
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: vesselLink.open()
                }
            }
        }
        Label {
            width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: root.smallTextSize
            text: root.ship ? root.ship.type + " · " + root.ship.timeSource + " · " + Model.age(root.ship.lastSeen, root.now) + (root.ship.stale ? " · OLD POSITION" : "") : ""
            color: root.ship && root.ship.stale ? Color.accent : Color.muted
        }
    }
    DetailRow {
        width: parent.width; bold: true
        fields: [
            {label: "DISTANCE", value: root.ship ? Model.distance(root.ship.distance, root.unit) : ""},
            {label: "BEARING", value: root.ship ? Model.compass(root.ship.bearing) + " " + Math.round(root.ship.bearing) + "°" : ""},
            {label: "SPEED", value: root.ship && root.ship.speed !== null ? root.ship.speed.toFixed(1) + " kn" : ""}
        ]
    }
    DetailRow {
        objectName: "navigationDetails"
        width: parent.width
        fields: [
            {label: "STATUS", value: root.ship ? root.ship.status || "" : ""},
            {label: "COURSE", value: root.ship && root.ship.course !== null && root.ship.course !== undefined ? Math.round(root.ship.course) + "°" : ""},
            {label: "SIZE", value: Model.hullSize(root.ship)}
        ]
    }
    DetailRow {
        objectName: "identityDetails"
        width: parent.width
        fields: [
            {label: "DESTINATION", value: root.ship ? (root.ship.destination || "").trim() : ""},
            {label: "MMSI", value: root.ship ? root.ship.mmsi : ""},
            {label: "IMO", value: vesselLink.hasImo ? String(root.ship.imo) : ""}
        ]
    }
    DetailRow {
        objectName: "voyageDetails"
        width: parent.width
        fields: [
            {label: "ETA", value: root.ship ? root.ship.eta || "" : ""},
            {label: "CALL SIGN", value: root.ship ? root.ship.callSign || "" : ""},
            {label: "DRAUGHT", value: root.ship && root.ship.draught ? root.ship.draught.toFixed(1) + " m" : ""}
        ]
    }
    Rectangle { width: parent.width; height: 1; color: Color.muted; opacity: 0.2 }
}
