pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Share one receiver across all widget instances in this QML engine.
Item {
    id: root
    property var report: ({status: "SETUP", ships: [], total: 0, error: ""})
    // Retain static geography between snapshots without repainting it every second.
    property var basemap: ({available: false, polygons: [], coastlines: []})
    property var config: ({})
    property var preferences: ({radiusNm: 25, autoLocation: true, demo: false, unit: "nm", hasApiKey: false})
    property bool saving: false
    property string settingsError: ""
    signal settingsSaved()
    property string signature: ""
    // Reference counting stops the helper when the last bar instance disappears.
    property int users: 0
    property bool pendingRestart: false
    property bool stopping: false
    readonly property var ships: report.ships || []
    // Resolve relative to this plugin, not the shell working directory; decode spaces in paths.
    readonly property string helper: decodeURIComponent(Qt.resolvedUrl("backend/vessel.py").toString().replace(/^file:\/\//, ""))
    function attach(settings) { users++; configure(settings); loadSettings(); }
    function detach() {
        users = Math.max(0, users - 1);
        if (users === 0) { stopping = true; pendingRestart = false; process.running = false; }
    }
    // Compare only receiver settings so display-only changes do not reconnect the stream.
    function configure(settings) {
        var next = {pythonExecutable: settings.pythonExecutable || "python3"};
        var key = JSON.stringify(next);
        if (key === signature && (process.running || pendingRestart)) return;
        config = next; signature = key; restart();
    }
    // Wait for the old process to exit before launching its replacement.
    function restart() {
        report = {status: "STARTING", ships: [], total: 0, error: ""};
        basemap = {available: false, polygons: [], coastlines: []};
        stopping = false;
        if (process.running) { pendingRestart = true; process.running = false; }
        else startTimer.restart();
    }
    function start() {
        if (users === 0) return;
        pendingRestart = false;
        // Credentials are read by Python from user storage, never from argv.
        var args = [config.pythonExecutable, "-B", helper, "--saved-settings"];
        process.command = args;
        process.running = true;
        startupWatch.restart();
    }
    function loadSettings() {
        if (settingsProcess.running) return;
        settingsProcess.command = [config.pythonExecutable || "python3", "-B", helper, "--read-settings"];
        settingsProcess.running = true;
    }
    function saveSettings(values) {
        if (settingsProcess.running) return;
        settingsError = ""; saving = true;
        settingsProcess.payload = JSON.stringify(values);
        settingsProcess.command = [config.pythonExecutable || "python3", "-B", helper, "--save-settings"];
        settingsProcess.running = true;
    }
    Process {
        id: settingsProcess
        property string payload: ""
        property bool received: false
        stdinEnabled: true
        onStarted: {
            received = false;
            if (payload) { write(payload + "\n"); payload = ""; }
        }
        stdout: SplitParser {
            onRead: data => {
                try {
                    var reply = JSON.parse(data);
                    settingsProcess.received = true;
                    if (reply.ok) {
                        root.preferences = reply.settings;
                        if (root.saving) { root.settingsSaved(); root.restart(); }
                    } else root.settingsError = reply.error;
                } catch (_) { root.settingsError = "Could not read the settings response."; }
            }
        }
        onExited: {
            payload = "";
            if (!received) root.settingsError = "Could not start settings helper. Check your Python executable.";
            root.saving = false;
        }
    }
    Timer { id: startTimer; interval: 100; onTriggered: root.start() }
    // A missing Python executable may fail before it can emit a structured setup error.
    Timer {
        id: startupWatch
        interval: 15000
        onTriggered: {
            if (root.report.status === "STARTING")
                root.report = {status: "SETUP", ships: [], total: 0, error: "Could not start Python. Check pythonExecutable in the widget settings."};
        }
    }
    Process {
        id: process
        // The helper emits complete snapshots; replacing the object updates QML bindings.
        stdout: SplitParser {
            onRead: data => {
                // Discard trailing output from a receiver that is being replaced or stopped.
                if (root.pendingRestart || root.stopping) return;
                try {
                    var next = JSON.parse(data);
                    if (next.status && Array.isArray(next.ships)) {
                        if (next.basemap) root.basemap = next.basemap;
                        root.report = next;
                    }
                } catch (_) { /* Ignore partial/non-protocol output. */ }
            }
        }
        // Preserve actionable setup/rejection messages instead of replacing them with a generic exit.
        onExited: {
            if (root.pendingRestart) startTimer.restart();
            else if (!root.stopping && root.report.status !== "SETUP" && root.report.status !== "REJECTED")
                root.report = {status: "STOPPED", ships: [], total: 0, error: "The receiver stopped. Check Python and your settings, then reconnect."};
        }
    }
}
