import QtQuick
import QtQuick.Controls.Basic
import qs.Commons

// The password lives in this editor only until Save/Cancel. Python never sends a
// saved credential back to QML; an empty field preserves the existing key.
Column {
    id: root
    spacing: 12
    property string family: "monospace"
    signal done()
    function populate() {
        var value = VesselService.preferences;
        apiKey.text = "";
        radius.text = String(value.radiusNm || 25);
        latitude.text = value.latitude === null || value.latitude === undefined ? "" : String(value.latitude);
        longitude.text = value.longitude === null || value.longitude === undefined ? "" : String(value.longitude);
        automatic.checked = value.autoLocation !== false;
        demo.checked = value.demo === true;
        kilometres.checked = value.unit === "km";
    }
    Component.onCompleted: populate()
    Connections {
        target: VesselService
        function onSettingsSaved() { apiKey.text = ""; root.done(); }
        function onPreferencesChanged() { root.populate(); }
    }
    onVisibleChanged: { if (visible) populate(); else apiKey.text = ""; }
    component Caption: Text {
        color: Color.foreground; font.family: root.family; font.pixelSize: 12
        textFormat: Text.PlainText; wrapMode: Text.WordWrap; width: parent.width
    }
    component Field: TextField {
        width: parent.width; height: 38
        color: Color.foreground; placeholderTextColor: Color.muted
        font.family: root.family; font.pixelSize: 13
        selectionColor: Color.accent; selectedTextColor: Color.background
        selectByMouse: true
        background: Rectangle { color: Color.background; border.color: parent.activeFocus ? Color.accent : Color.muted; radius: 3 }
    }
    component Action: Button {
        font.family: root.family
        contentItem: Text { text: parent.text; color: Color.accent; font: parent.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { color: Color.background; border.color: Color.accent; radius: 3; opacity: parent.enabled ? 1 : 0.4 }
    }
    component Toggle: CheckBox {
        font.family: root.family
        contentItem: Text { text: parent.text; color: Color.foreground; font: parent.font; leftPadding: 30; verticalAlignment: Text.AlignVCenter }
        indicator: Rectangle {
            width: 18; height: 18; y: (parent.height - height) / 2
            color: Color.background; border.color: Color.accent
            Rectangle { anchors.centerIn: parent; width: 10; height: 10; color: Color.accent; visible: parent.parent.checked }
        }
    }
    Caption { text: "V E S S E L  /  SETTINGS"; color: Color.accent; font.bold: true }
    Caption { text: "AISStream API key" }
    Field {
        id: apiKey; echoMode: TextInput.Password
        placeholderText: VesselService.preferences.hasApiKey ? "Key saved · leave blank to keep it" : "Paste your API key"
        maximumLength: 4096
    }
    Action { text: "GET AN API KEY ↗"; onClicked: Qt.openUrlExternally("https://aisstream.io/account") }
    Caption { text: "Sign in with GitHub, create a key, then paste it above. Your key is stored locally with owner-only permissions."; color: Color.muted }
    Toggle { id: demo; text: "Offline demo · Genova" }
    Toggle { id: automatic; text: "Approximate location via IP"; enabled: !demo.checked }
    Caption { text: "Fixed latitude / longitude"; visible: !automatic.checked && !demo.checked }
    Row {
        width: parent.width; spacing: 8; visible: !automatic.checked && !demo.checked
        Field { id: latitude; width: (parent.width - 8) / 2; placeholderText: "44.4056" }
        Field { id: longitude; width: (parent.width - 8) / 2; placeholderText: "8.9463" }
    }
    Caption { text: "Radius in nautical miles (1–200)" }
    Field { id: radius; placeholderText: "25" }
    Toggle { id: kilometres; text: "Display distances in kilometres" }
    Caption { text: VesselService.settingsError; visible: text.length > 0; color: Color.accent }
    Row {
        spacing: 12
        Action {
            text: VesselService.saving ? "SAVING…" : "SAVE & CONNECT"
            enabled: !VesselService.saving
            onClicked: {
                VesselService.saveSettings({apiKey: apiKey.text, radiusNm: radius.text,
                    latitude: latitude.text, longitude: longitude.text,
                    autoLocation: automatic.checked, demo: demo.checked,
                    unit: kilometres.checked ? "km" : "nm"});
                apiKey.text = "";
            }
        }
        Action { text: "CANCEL"; enabled: !VesselService.saving; onClicked: { apiKey.text = ""; root.done(); } }
    }
}
