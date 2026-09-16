import QtQuick
import Quickshell
import QtQuick.Controls.Basic
import qs.Commons

// The password lives in this editor only until Save/Cancel. Python never sends a
// saved credential back to QML; an empty field preserves the existing key.
Column {
    id: root
    spacing: 12
    property string cityName: ""
    property string family: "monospace"
    signal done()
    // Use Omarchy's session-aware launcher; Qt URL dispatch may not reach the
    // browser from the shell process. Pass arguments directly, without a shell.
    function openBrowser(url) {
        Quickshell.execDetached(["omarchy-launch-browser", url]);
    }
    function populate() {
        var value = VesselService.preferences;
        apiKey.text = "";
        radius.text = String(value.radiusNm || 25);
        latitude.text = value.latitude === null || value.latitude === undefined ? "" : String(value.latitude);
        longitude.text = value.longitude === null || value.longitude === undefined ? "" : String(value.longitude);
        root.cityName = value.cityName || "";
        city.text = root.cityName;
        manual.checked = !root.cityName && latitude.text !== "" && longitude.text !== "";
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
    onVisibleChanged: { if (visible) populate(); else { apiKey.text = ""; VesselService.clearCitySearch(); } }
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
        contentItem: Text { textFormat: Text.PlainText; text: parent.text; color: Color.accent; font: parent.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { color: Color.background; border.color: Color.accent; radius: 3; opacity: parent.enabled ? 1 : 0.4 }
    }
    component Toggle: CheckBox {
        font.family: root.family
        contentItem: Text { textFormat: Text.PlainText; text: parent.text; color: Color.foreground; font: parent.font; leftPadding: 30; verticalAlignment: Text.AlignVCenter }
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
    Action { objectName: "getApiKey"; text: "GET AN API KEY ↗"; onClicked: root.openBrowser("https://aisstream.io/account") }
    Caption { text: "Sign in with GitHub, create a key, then paste it above. Your key is stored locally with owner-only permissions."; color: Color.muted }
    Toggle { id: demo; text: "Offline demo · Genoa (Italy)" }
    Toggle { id: automatic; text: "Approximate location via IP"; enabled: !demo.checked }
    Column {
        width: parent.width; spacing: 8
        visible: !automatic.checked && !demo.checked
        Caption { text: "City" }
        Row {
            width: parent.width; spacing: 8
            visible: !manual.checked
            Field {
                id: city
                width: parent.width - searchButton.width - parent.spacing
                placeholderText: "Genoa, Italy"; maximumLength: 120
                onTextEdited: {
                    root.cityName = ""; latitude.text = ""; longitude.text = "";
                    VesselService.clearCitySearch();
                }
                onAccepted: if (text.trim().length >= 2) VesselService.searchCity(text)
            }
            Action {
                id: searchButton
                height: city.height
                text: VesselService.searchingCity ? "SEARCHING…" : "SEARCH"
                enabled: !VesselService.searchingCity && city.text.trim().length >= 2
                onClicked: VesselService.searchCity(city.text)
            }
        }
        Repeater {
            model: manual.checked ? [] : VesselService.cityResults
            delegate: Action {
                required property var modelData
                width: parent.width
                text: modelData.label + (modelData.detail ? " · " + modelData.detail : "")
                contentItem: Text {
                    text: parent.text; textFormat: Text.PlainText
                    color: Color.foreground; font.family: root.family; font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
                onClicked: {
                    root.cityName = modelData.label;
                    city.text = modelData.label;
                    latitude.text = String(modelData.latitude);
                    longitude.text = String(modelData.longitude);
                    VesselService.clearCitySearch();
                }
            }
        }
        Caption { text: root.cityName ? "Selected: " + root.cityName : "Search, then choose a city from the results."; visible: !manual.checked; color: Color.muted }
        Caption { text: VesselService.cityError; visible: !manual.checked && text.length > 0; color: Color.accent }
        Caption {
            text: "City search: Photon / © OpenStreetMap contributors ↗"
            font.pixelSize: 10; color: Color.muted; visible: !manual.checked
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.openBrowser("https://www.openstreetmap.org/copyright") }
        }
        Toggle {
            id: manual; text: "Enter coordinates instead"
            onToggled: { if (checked) root.cityName = ""; VesselService.clearCitySearch(); }
        }
        Row {
            width: parent.width; spacing: 8; visible: manual.checked
            Field { id: latitude; width: (parent.width - 8) / 2; placeholderText: "Latitude"; onTextEdited: root.cityName = "" }
            Field { id: longitude; width: (parent.width - 8) / 2; placeholderText: "Longitude"; onTextEdited: root.cityName = "" }
        }
    }
    Caption { text: "Radius in nautical miles (1–200)" }
    Field { id: radius; placeholderText: "25" }
    Toggle { id: kilometres; text: "Display distances in kilometres" }
    Caption { text: VesselService.settingsError; visible: text.length > 0; color: Color.accent }
    Row {
        spacing: 12
        Action {
            text: VesselService.saving ? "SAVING…" : "SAVE & CONNECT"
            enabled: !VesselService.saving && (demo.checked || automatic.checked || manual.checked || root.cityName.length > 0)
            onClicked: {
                VesselService.saveSettings({apiKey: apiKey.text, radiusNm: radius.text,
                    latitude: latitude.text, longitude: longitude.text, cityName: root.cityName,
                    autoLocation: automatic.checked, demo: demo.checked,
                    unit: kilometres.checked ? "km" : "nm"});
                apiKey.text = "";
            }
        }
        Action { text: "CANCEL"; enabled: !VesselService.saving; onClicked: { apiKey.text = ""; root.done(); } }
    }
}
