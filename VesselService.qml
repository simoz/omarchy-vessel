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
    property var mapDetail: ({available: false})
    // wantedDetail is the latest viewport, even while an older request runs.
    // completedDetail suppresses duplicate requests; failures become retryable.
    property string wantedDetail: ""
    property string completedDetail: ""
    property double detailRetryAt: 0
    // Separate process: map navigation never reconnects or blocks reception.
    function requestDetail(query) {
        wantedDetail = query ? JSON.stringify(query) : "";
        if (viewers === 0 || !wantedDetail || detailProcess.running)
            return;
        var alreadyCompleted = wantedDetail === completedDetail;
        var retryAllowed = Date.now() >= detailRetryAt;
        if (!alreadyCompleted || retryAllowed)
            startDetail();
    }
    function startDetail() {
        if (viewers === 0 || !wantedDetail) return;
        detailProcess.query = wantedDetail;
        detailProcess.received = false;
        detailProcess.command = helperCommand(["--map-detail"]);
        detailProcess.running = true;
    }
    Process {
        id: detailProcess
        property string query: ""
        property bool received: false
        stdinEnabled: true
        onStarted: write(query + "\n")
        stdout: SplitParser {
            onRead: data => {
                // Never install a response for a view the user has already left.
                if (root.viewers === 0 || detailProcess.query !== root.wantedDetail) return;
                try {
                    var result = JSON.parse(data);
                    detailProcess.received = true;
                    root.completedDetail = detailProcess.query;
                    // Successful data stays reusable until the viewport changes.
                    root.detailRetryAt = result.available ? Number.POSITIVE_INFINITY : Date.now() + 30000;
                    if (result.available) root.mapDetail = result;
                } catch (_) { /* Retain the last complete map on a failed batch. */ }
            }
        }
        onExited: {
            if (root.viewers === 0) return;
            // Coalesce a burst of navigation into one follow-up for the latest view.
            if (query !== root.wantedDetail) root.startDetail();
            else if (!received) {
                root.completedDetail = query;
                root.detailRetryAt = Date.now() + 30000;
            }
        }
    }
    // Receiver ownership, user preferences and settings/search feedback.
    property var config: ({})
    property var preferences: ({provider: "openwaters", radiusNm: 25, autoLocation: true, unit: "nm", hasApiKey: false, hasOpenwatersKey: false})
    readonly property bool searchingCity: cityProcess.running
    property var cityResults: []
    property var cityCache: []
    property string cityQuery: ""
    property string cityError: ""
    property double lastCitySearch: 0
    property bool saving: false
    property string settingsError: ""
    signal settingsSaved()
    property string signature: ""
    // Reference counting stops the helper when the last bar instance disappears.
    property int users: 0
    property int viewers: 0
    // Count open views across monitors independently from installed bar widgets.
    function setViewing(visible) {
        viewers = Math.max(0, viewers + (visible ? 1 : -1));
        if (viewers === 0) {
            stopReceiver();
            wantedDetail = "";
            detailProcess.running = false;
            clearCitySearch();
            if (!paused && report.status !== "SETUP") {
                var snapshot = Object.assign({}, report);
                snapshot.status = "STOPPED";
                report = snapshot;
            }
        } else if (visible && viewers === 1 && !paused) restart();
    }
    property bool pendingRestart: false
    property bool stopping: false
    property bool paused: false
    readonly property var ships: report.ships || []
    // Resolve relative to this plugin, not the shell working directory; decode spaces in paths.
    readonly property string helper: decodeURIComponent(Qt.resolvedUrl("backend/vessel.py").toString().replace(/^file:\/\//, ""))
    // All helpers use an argument list, never shell interpolation. Keep the
    // credential-bearing save payload on stdin rather than the process list.
    function helperCommand(extraArgs) {
        return [config.pythonExecutable || "python3", "-B", helper].concat(extraArgs);
    }
    function attach(settings) {
        users++;
        configure(settings);
        loadSettings();
    }
    function stopReceiver() {
        stopping = true;
        pendingRestart = false;
        startTimer.stop();
        startupWatch.stop();
        process.running = false;
    }
    function detach() {
        users = Math.max(0, users - 1);
        if (users === 0) {
            stopReceiver();
            clearCitySearch();
        }
    }
    // Compare only receiver settings so display-only changes do not reconnect the stream.
    function configure(settings) {
        var next = {pythonExecutable: settings.pythonExecutable || "python3"};
        var key = JSON.stringify(next);
        if (key === signature && (process.running || pendingRestart || startTimer.running || paused)) return;
        config = next; signature = key;
        if (!paused) restart();
    }
    // Pause closes the receiver, rather than merely hiding updates. Keep the
    // last snapshot and map so users can inspect them, clearly marked PAUSED.
    function pause() {
        if (paused) return;
        paused = true;
        stopReceiver();
        var snapshot = Object.assign({}, report);
        snapshot.status = "PAUSED";
        report = snapshot;
    }
    function togglePaused() {
        if (paused) restart();
        else pause();
    }
    // Wait for the old process to exit before launching its replacement.
    function restart() {
        paused = false;
        if (viewers === 0) { stopReceiver(); return; }
        report = {status: "STARTING", ships: [], total: 0, error: ""};
        basemap = {available: false, polygons: [], coastlines: []};
        mapDetail = {available: false};
        wantedDetail = ""; completedDetail = "";
        stopping = false;
        if (process.running) { pendingRestart = true; process.running = false; }
        else startTimer.restart();
    }
    function start() {
        if (users === 0 || viewers === 0 || paused || stopping) return;
        pendingRestart = false;
        // Credentials are read by Python from user storage, never from argv.
        process.command = helperCommand(["--saved-settings"]);
        process.running = true;
        startupWatch.restart();
    }
    function loadSettings() {
        if (settingsProcess.running) return;
        settingsProcess.received = false;
        settingsProcess.command = helperCommand(["--read-settings"]);
        settingsProcess.running = true;
    }
    // Persist first; settingsSaved lets the editor close before reception restarts.
    function saveSettings(values) {
        if (settingsProcess.running) return;
        settingsError = ""; saving = true;
        settingsProcess.payload = JSON.stringify(values);
        settingsProcess.received = false;
        settingsProcess.command = helperCommand(["--save-settings"]);
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
    function clearCitySearch() {
        cityQuery = ""; cityResults = []; cityError = "";
        if (cityProcess.running) cityProcess.running = false;
    }
    function searchCity(query) {
        query = query.trim();
        if (viewers === 0 || cityProcess.running || query.length < 2) return;
        cityResults = []; cityError = ""; cityQuery = query;
        // Session cache avoids repeat network requests; saved cities never need re-geocoding.
        for (var i = 0; i < cityCache.length; i++) {
            if (cityCache[i].query === query.toLowerCase()) {
                cityResults = cityCache[i].places;
                if (!cityResults.length) cityError = "No cities found. Try adding the country.";
                return;
            }
        }
        if (Date.now() - lastCitySearch < 1100) { cityError = "Please wait a moment before searching again."; return; }
        lastCitySearch = Date.now();
        cityProcess.received = false;
        cityProcess.command = helperCommand(["--search-city", query]);
        cityProcess.running = true;
    }
    Process {
        id: cityProcess
        property bool received: false
        stdout: SplitParser {
            onRead: data => {
                try {
                    var reply = JSON.parse(data);
                    // Ignore results after the user edits the query or leaves Settings.
                    if (reply.query !== root.cityQuery) return;
                    cityProcess.received = true;
                    if (reply.ok && Array.isArray(reply.places)) {
                        root.cityResults = reply.places;
                        root.cityCache = root.cityCache.slice(-19).concat([{query: root.cityQuery.toLowerCase(), places: reply.places}]);
                        if (!reply.places.length) root.cityError = "No cities found. Try adding the country.";
                    } else root.cityError = reply.error || "City search unavailable.";
                } catch (_) { root.cityError = "Could not read city search results."; }
            }
        }
        onExited: {
            if (!received && root.cityQuery) root.cityError = "City search stopped. Please try again.";
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
    // Reception snapshots are independent from the detail-map and settings replies.
    Process {
        id: process
        // The helper emits complete snapshots; replacing the object updates QML bindings.
        stdout: SplitParser {
            onRead: data => {
                // Discard trailing output from a receiver that is being replaced or stopped.
                if (root.pendingRestart || root.stopping || root.paused) return;
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
