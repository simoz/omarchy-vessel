// Keep the help sheet and shortcut dispatch together. Modified shortcuts belong
// to the desktop or text editor; Shift and keypad keys remain valid here.
var hints = [
    [["W", "A", "S", "D"], "Pan (arrows too)"],
    [["+", "−"], "Zoom (= too)"],
    [["0", "Home"], "Reset to your location"],
    [[",", "."], "Previous / next vessel"],
    [["Space", "P"], "Pause / resume reception"],
    [["R"], "Reconnect (Enter too)"],
    [["F"], "Expand / widget"],
    [["<"], "Settings"],
    [["PgUp", "PgDn"], "Scroll panel"],
    [["Tab"], "Next control (Shift: previous)"],
    [["Enter", "Space"], "Activate focused control"],
    [["?", "F1"], "This sheet · Esc closes"]
];

function command(key, text, modifiers) {
    if (modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)) return "";
    if (text === "?" || key === Qt.Key_F1) return "help";
    if (key === Qt.Key_Escape) return "dismiss";
    if (key === Qt.Key_Left) return "left";
    if (key === Qt.Key_Right) return "right";
    if (key === Qt.Key_Up) return "up";
    if (key === Qt.Key_Down) return "down";
    if (key === Qt.Key_Home) return "center";
    if (key === Qt.Key_PageUp) return "pageUp";
    if (key === Qt.Key_PageDown) return "pageDown";
    if (key === Qt.Key_Return || key === Qt.Key_Enter) return "reconnect";
    var commands = {"h":"left", "j":"down", "k":"up", "l":"right",
        "w":"up", "a":"left", "s":"down", "d":"right",
        "+":"zoomIn", "=":"zoomIn", "-":"zoomOut", "0":"center",
        ",":"previous", ".":"next", " ":"pause", "p":"pause",
        "r":"reconnect", "<":"settings", "f":"expand"};
    return commands[(text || "").toLowerCase()] || "";
}
