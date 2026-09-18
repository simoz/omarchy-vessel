import QtQuick
import qs.Commons

// A compact side-profile ship for the bar, separate from radar contact markers.
Canvas {
    id: root
    implicitWidth: 16
    implicitHeight: 16
    property color ink: Color.foreground
    onInkChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var c = getContext("2d"); c.reset();
        c.scale(width / 24, height / 24);
        c.strokeStyle = ink; c.lineWidth = 1.9;
        c.lineJoin = "round"; c.lineCap = "round";
        c.beginPath();
        c.moveTo(3, 13); c.lineTo(21, 13);
        c.lineTo(17, 19); c.lineTo(7, 19);
        c.closePath(); c.stroke();
        c.beginPath();
        c.moveTo(7, 13); c.lineTo(7, 8); c.lineTo(16, 8); c.lineTo(16, 13);
        c.moveTo(10, 8); c.lineTo(10, 5); c.lineTo(13, 5); c.lineTo(13, 8);
        c.stroke();
    }
}
