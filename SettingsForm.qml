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
    property string locationMode: "city"
    property bool editingKey: false
    property string provider: "openwaters"
    readonly property bool hasProviderKey: provider === "openwaters"
        ? !!VesselService.preferences.hasOpenwatersKey : !!VesselService.preferences.hasApiKey
    readonly property bool canSave: !VesselService.saving
        && (provider === "openwaters" || hasProviderKey || apiKey.text.trim().length > 0)
        && (locationMode === "ip" || (locationMode === "coordinates"
            ? latitude.text.trim().length > 0 && longitude.text.trim().length > 0 : cityName.length > 0))
    property string family: "monospace"
    signal done()
    signal focusRequested(var item)
    function focusFirst() {
        if (locationMode === "city") city.forceActiveFocus();
        else if (locationMode === "coordinates") latitude.forceActiveFocus();
        else ipMode.forceActiveFocus();
    }
    // Build one payload from the active modes; hidden fields never decide the mode.
    function save() {
        if (!canSave) return;
        var values = {provider: provider, radiusNm: radius.text,
            latitude: latitude.text, longitude: longitude.text,
            cityName: locationMode === "city" ? cityName : "",
            autoLocation: locationMode === "ip",
            unit: kilometres.checked ? "km" : miles.checked ? "mi" : "nm"};
        values[provider === "openwaters" ? "openwatersKey" : "apiKey"] = apiKey.text;
        VesselService.saveSettings(values);
        apiKey.text = "";
    }
    function cancel() {
        apiKey.text = "";
        done();
    }
    function chooseMode(mode) {
        locationMode = mode;
        VesselService.clearCitySearch();
        Qt.callLater(() => focusFirst());
    }
    // Use Omarchy's session-aware launcher; Qt URL dispatch may not reach the
    // browser from the shell process. Pass arguments directly, without a shell.
    function openBrowser(url) {
        Quickshell.execDetached(["omarchy-launch-browser", url]);
    }
    // Public preferences contain only key-presence flags, never stored credentials.
    function populate() {
        var value = VesselService.preferences;
        root.provider = value.provider || "openwaters";
        apiKey.text = "";
        radius.text = String(value.radiusNm || 25);
        latitude.text = value.latitude === null || value.latitude === undefined ? "" : String(value.latitude);
        longitude.text = value.longitude === null || value.longitude === undefined ? "" : String(value.longitude);
        root.cityName = value.cityName || "";
        city.text = root.cityName;
        root.locationMode = value.autoLocation !== false ? "ip"
            : root.cityName ? "city" : latitude.text !== "" && longitude.text !== "" ? "coordinates" : "city";
        root.editingKey = !root.hasProviderKey;
        nautical.checked = value.unit !== "km" && value.unit !== "mi";
        kilometres.checked = value.unit === "km";
        miles.checked = value.unit === "mi";
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
        id: editor
        property bool selectOnFocus: false
        focusPolicy: Qt.StrongFocus
        onActiveFocusChanged: if (activeFocus) {
            root.focusRequested(editor);
            // Run after the mouse press has positioned the cursor.
            if (selectOnFocus) Qt.callLater(() => { if (editor.activeFocus) editor.selectAll(); });
        }
        width: parent.width; height: 38
        color: Color.foreground; placeholderTextColor: Color.muted
        font.family: root.family; font.pixelSize: 13
        selectionColor: Color.accent; selectedTextColor: Color.background
        selectByMouse: true
        background: Rectangle { color: Color.background; border.color: parent.activeFocus ? Color.accent : Color.muted; radius: 3 }
    }
    component Action: Button {
        focusPolicy: Qt.StrongFocus
        onActiveFocusChanged: if (activeFocus) root.focusRequested(this)
        font.family: root.family
        contentItem: Text { textFormat: Text.PlainText; text: parent.text; color: Color.accent; font: parent.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { color: Color.background; border.color: parent.activeFocus ? Color.foreground : Color.accent; border.width: parent.activeFocus ? 2 : 1; radius: 3; opacity: parent.enabled ? 1 : 0.4 }
    }
    // Sibling radio buttons keep the three unit choices mutually exclusive.
    component UnitOption: RadioButton {
        focusPolicy: Qt.StrongFocus
        onActiveFocusChanged: if (activeFocus) root.focusRequested(this)
        font.family: root.family
        contentItem: Text {
            text: parent.text; textFormat: Text.PlainText; color: Color.foreground
            font: parent.font; leftPadding: 30; verticalAlignment: Text.AlignVCenter
        }
        indicator: Rectangle {
            width: 18; height: 18; radius: 9; y: (parent.height - height) / 2
            color: Color.background; border.color: parent.activeFocus ? Color.foreground : Color.accent
            Rectangle {
                anchors.centerIn: parent; width: 8; height: 8; radius: 4
                color: Color.accent; visible: parent.parent.checked
            }
        }
    }
    Caption { text: "VESSEL / SETTINGS"; color: Color.accent; font.bold: true }
    Caption { text: "LOCATION"; color: Color.muted; font.pixelSize: 10 }
    Row {
        width: parent.width; spacing: 6
        component Mode: Action {
            property string mode
            width: (parent.width - 12) / 3
            checked: root.locationMode === mode
            background: Rectangle {
                color: parent.checked ? Qt.alpha(Color.accent, 0.15) : Color.background
                border.color: parent.activeFocus ? Color.foreground : parent.checked ? Color.accent : Color.muted
                radius: 3
            }
            onClicked: root.chooseMode(mode)
        }
        Mode { text: "CITY"; mode: "city" }
        Mode { id: ipMode; text: "IP LOCATION"; mode: "ip" }
        Mode { text: "COORDINATES"; mode: "coordinates" }
    }
    Column {
        width: parent.width; spacing: 8
        visible: root.locationMode === "city"
        Row {
            width: parent.width; spacing: 8
            Field {
                id: city
                objectName: "settingsCity"
                selectOnFocus: true
                width: parent.width - searchButton.width - parent.spacing
                placeholderText: "Search a city, e.g. Genoa, Italy"; maximumLength: 120
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
            model: root.locationMode === "city" ? VesselService.cityResults : []
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
        Caption { text: root.cityName ? "Selected: " + root.cityName : "Search, then choose a city from the results."; color: Color.muted }
        Caption { text: VesselService.cityError; visible: text.length > 0; color: Color.accent }
        Action {
            text: "City search: Photon / © OpenStreetMap contributors ↗"
            font.pixelSize: 10
            onClicked: root.openBrowser("https://www.openstreetmap.org/copyright")
        }
    }
    Caption {
        visible: root.locationMode === "ip"
        text: "Uses your public IP to estimate your location. A VPN may place you elsewhere."
        color: Color.muted
    }
    Row {
        width: parent.width; spacing: 8; visible: root.locationMode === "coordinates"
        Field { id: latitude; width: (parent.width - 8) / 2; placeholderText: "Latitude"; onTextEdited: root.cityName = "" }
        Field { id: longitude; width: (parent.width - 8) / 2; placeholderText: "Longitude"; onTextEdited: root.cityName = "" }
    }
    Rectangle { width: parent.width; height: 1; color: Color.muted; opacity: 0.3 }
    Caption { text: "COVERAGE"; color: Color.muted; font.pixelSize: 10 }
    Caption { text: "Radius in nautical miles (1–200)" }
    Field { id: radius; placeholderText: "25" }
    Caption { text: "Distance units" }
    Row {
        width: parent.width; spacing: 12
        UnitOption { id: nautical; objectName: "unitNm"; text: "nm" }
        UnitOption { id: kilometres; objectName: "unitKm"; text: "km" }
        UnitOption { id: miles; objectName: "unitMi"; text: "mi" }
    }
    Caption { text: "Speed is shown in knots (kn)."; color: Color.muted }
    Rectangle { width: parent.width; height: 1; color: Color.muted; opacity: 0.3 }
    Caption { text: "AIS CONNECTION"; color: Color.muted; font.pixelSize: 10 }
    Row {
        width: parent.width; spacing: 12
        UnitOption {
            text: "OpenWaters"; checked: root.provider === "openwaters"
            onClicked: { root.provider = "openwaters"; apiKey.text = ""; root.editingKey = !root.hasProviderKey; }
        }
        UnitOption {
            text: "AISStream"; checked: root.provider === "aisstream"
            onClicked: { root.provider = "aisstream"; apiKey.text = ""; root.editingKey = !root.hasProviderKey; }
        }
    }
    Caption {
        text: root.provider === "openwaters"
            ? "Ready without an account. An optional personal token raises the limits."
            : "Sign in with GitHub to create a free AISStream key."
        color: Color.muted
    }
    Row {
        width: parent.width; spacing: 12
        visible: root.hasProviderKey && !root.editingKey
        Caption { width: parent.width - editKey.width - 12; text: "Credential saved"; anchors.verticalCenter: parent.verticalCenter }
        Action {
            id: editKey
            text: "CHANGE"
            onClicked: { root.editingKey = true; Qt.callLater(() => apiKey.forceActiveFocus()); }
        }
    }
    Field {
        id: apiKey; objectName: "settingsApiKey"; echoMode: TextInput.Password
        visible: root.editingKey
        placeholderText: root.hasProviderKey ? "Leave blank to keep the saved credential"
            : root.provider === "openwaters" ? "Optional OpenWaters token" : "Paste your AISStream API key"
        maximumLength: 4096
    }
    Action {
        objectName: "getApiKey"
        text: root.provider === "openwaters" ? "OPENWATERS / TOKEN ↗" : "GET AN API KEY ↗"
        onClicked: root.openBrowser(root.provider === "openwaters" ? "https://openwaters.io/ais/" : "https://aisstream.io/account")
    }
    Caption { text: VesselService.settingsError; visible: text.length > 0; color: Color.accent }
}
