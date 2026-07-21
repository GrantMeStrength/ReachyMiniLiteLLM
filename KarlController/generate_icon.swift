import AppKit

guard CommandLine.arguments.count == 2 else {
    fatalError("Usage: generate_icon.swift <output.png>")
}

let size = NSSize(width: 1024, height: 1024)
let image = NSImage(size: size)
image.lockFocus()

let background = NSGradient(colors: [
    NSColor(red: 0.10, green: 0.24, blue: 0.42, alpha: 1),
    NSColor(red: 0.10, green: 0.55, blue: 0.66, alpha: 1)
])
let tile = NSBezierPath(
    roundedRect: NSRect(x: 52, y: 52, width: 920, height: 920),
    xRadius: 210,
    yRadius: 210
)
background?.draw(in: tile, angle: -45)

NSColor.white.withAlphaComponent(0.95).setFill()
let head = NSBezierPath(
    roundedRect: NSRect(x: 210, y: 250, width: 604, height: 500),
    xRadius: 190,
    yRadius: 190
)
head.fill()

NSColor(red: 0.08, green: 0.20, blue: 0.33, alpha: 1).setFill()
NSBezierPath(ovalIn: NSRect(x: 315, y: 440, width: 130, height: 130)).fill()
NSBezierPath(ovalIn: NSRect(x: 579, y: 440, width: 130, height: 130)).fill()

let smile = NSBezierPath()
smile.lineWidth = 34
smile.lineCapStyle = .round
smile.move(to: NSPoint(x: 390, y: 370))
smile.curve(
    to: NSPoint(x: 634, y: 370),
    controlPoint1: NSPoint(x: 450, y: 310),
    controlPoint2: NSPoint(x: 574, y: 310)
)
smile.stroke()

let antenna = NSBezierPath()
antenna.lineWidth = 36
antenna.lineCapStyle = .round
antenna.move(to: NSPoint(x: 512, y: 748))
antenna.line(to: NSPoint(x: 512, y: 850))
antenna.stroke()
NSBezierPath(ovalIn: NSRect(x: 467, y: 826, width: 90, height: 90)).fill()

image.unlockFocus()

guard let data = image.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: data),
      let png = bitmap.representation(using: .png, properties: [:]) else {
    fatalError("Could not render app icon")
}
try png.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
