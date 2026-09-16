import QtQuick
import qs.Commons
import qs.Ui

// Separate hit target: pausing never opens the radar. The service is shared
// across monitors, so every instance shows the same reception state.
WidgetButton {
    id: root
    fixedWidth: Style.space(16) + scaledHorizontalMargin * 2
    labelVisible: false
    hasVisualContent: true
    tooltipText: VesselService.paused ? "AIS reception paused · Resume" : "Pause AIS reception"
    Accessible.role: Accessible.Button
    Accessible.name: tooltipText
    Accessible.onPressAction: VesselService.togglePaused()
    onPressed: function(b) { if (b === Qt.LeftButton) VesselService.togglePaused(); }
    Item {
        anchors.centerIn: parent; width: 12; height: 12
        // Geometry keeps both symbols centered independently of font metrics.
        Row {
            anchors.centerIn: parent; spacing: 3
            visible: !VesselService.paused
            Rectangle { width: 3; height: 10; color: root.foreground }
            Rectangle { width: 3; height: 10; color: root.foreground }
        }
        Canvas {
            anchors.fill: parent; visible: VesselService.paused
            property color ink: root.foreground
            onInkChanged: requestPaint()
            onPaint: {
                var c = getContext("2d"); c.reset();
                c.beginPath(); c.moveTo(2, 1); c.lineTo(11, 6); c.lineTo(2, 11); c.closePath();
                c.fillStyle = ink; c.fill();
            }
        }
    }
}
