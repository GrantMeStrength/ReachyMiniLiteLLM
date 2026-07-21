import SwiftUI

struct InteractionView: View {
    @Environment(RobotController.self) private var controller
    @State private var speechText = ""
    @State private var customEyeColor = Color(red: 0.1, green: 0.45, blue: 1)

    private let eyeColors = [
        ("Blue", "0,80,255", Color.blue),
        ("Green", "0,200,50", Color.green),
        ("Purple", "150,0,255", Color.purple),
        ("Amber", "255,150,0", Color.orange),
        ("White", "80,80,100", Color.white)
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Text("Interact")
                    .font(.largeTitle)
                    .bold()
                HStack(alignment: .top, spacing: 24) {
                    VStack(spacing: 20) {
                        speechControls
                        movementControls
                        eyeControls
                    }
                    cameraPanel
                }
            }
            .padding(28)
        }
        .navigationTitle("Interact")
    }

    private var speechControls: some View {
        GroupBox("Speech") {
            HStack {
                TextField("What should Karl say?", text: $speechText)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit(speak)
                Button("Speak", systemImage: "speaker.wave.2.fill", action: speak)
                    .buttonStyle(.borderedProminent)
            }
            .padding(.top, 6)
        }
    }

    private var movementControls: some View {
        GroupBox("Movement") {
            VStack(alignment: .leading, spacing: 12) {
                LabeledContent("Head Direction") {
                    VStack(spacing: 8) {
                        Button("Look Up", systemImage: "arrow.up") {
                            controller.look("up")
                        }
                        HStack {
                            Button("Look Left", systemImage: "arrow.left") {
                                controller.look("left")
                            }
                            Button("Center", systemImage: "scope") {
                                controller.look("center")
                            }
                            Button("Look Right", systemImage: "arrow.right") {
                                controller.look("right")
                            }
                        }
                        Button("Look Down", systemImage: "arrow.down") {
                            controller.look("down")
                        }
                    }
                }

                LabeledContent("Head Tilt") {
                    HStack {
                        Button("Tilt Left", systemImage: "rotate.left") {
                            controller.look("tilt-left")
                        }
                        Button("Tilt Right", systemImage: "rotate.right") {
                            controller.look("tilt-right")
                        }
                    }
                }

                LabeledContent("Body Rotation") {
                    HStack {
                        Button("Body Left", systemImage: "arrow.turn.up.left") {
                            controller.rotateBody("left")
                        }
                        Button("Body Center", systemImage: "scope") {
                            controller.rotateBody("center")
                        }
                        Button("Body Right", systemImage: "arrow.turn.up.right") {
                            controller.rotateBody("right")
                        }
                    }
                }

                LabeledContent("Antennas") {
                    HStack {
                        Button("Up", systemImage: "chevron.up.2") {
                            controller.positionAntennas("up")
                        }
                        Button("Neutral", systemImage: "minus") {
                            controller.positionAntennas("neutral")
                        }
                        Button("Down", systemImage: "chevron.down.2") {
                            controller.positionAntennas("down")
                        }
                    }
                }

                LabeledContent("Face Tracking") {
                    if controller.isFaceTracking {
                        Button("Stop Following", systemImage: "person.crop.circle.badge.xmark") {
                            controller.setFaceTracking(false)
                        }
                    } else {
                        Button("Follow Face", systemImage: "person.crop.circle.badge.checkmark") {
                            controller.setFaceTracking(true)
                        }
                    }
                }

                LabeledContent("Gestures") {
                    HStack {
                        Button("Nod Yes", systemImage: "checkmark") {
                            controller.nod()
                        }
                        Button("Shake No", systemImage: "xmark") {
                            controller.shake()
                        }
                        Button("Run Demo", systemImage: "sparkles") {
                            controller.demo()
                        }
                    }
                }

                LabeledContent("Emotions") {
                    HStack {
                        Button("Cheerful", systemImage: "face.smiling") {
                            controller.playEmotion("cheerful1", title: "Cheerful")
                        }
                        Button("Curious", systemImage: "questionmark") {
                            controller.playEmotion("curious1", title: "Curious")
                        }
                        Button("Laugh", systemImage: "theatermasks") {
                            controller.playEmotion("laughing1", title: "Laughing")
                        }
                        Button("Proud", systemImage: "medal") {
                            controller.playEmotion("proud1", title: "Proud")
                        }
                        Button("Dance", systemImage: "music.note") {
                            controller.playEmotion("dance1", title: "Dance")
                        }
                    }
                }
            }
            .buttonStyle(.bordered)
            .disabled(controller.isBusy || !controller.status.daemon)
            .padding(.top, 6)
        }
    }

    private var eyeControls: some View {
        GroupBox("LED Eyes") {
            VStack(alignment: .leading, spacing: 12) {
                LabeledContent("Presets") {
                    HStack {
                        ForEach(eyeColors, id: \.0) { name, value, color in
                            Button {
                                controller.setEyes(value)
                            } label: {
                                Label(name, systemImage: "circle.fill")
                                    .labelStyle(.iconOnly)
                                    .foregroundStyle(color)
                            }
                            .help(name)
                            .accessibilityLabel("\(name) eyes")
                        }
                    }
                }

                LabeledContent("Custom Color") {
                    HStack {
                        ColorPicker("Eye color", selection: $customEyeColor)
                            .labelsHidden()
                        Button("Apply") {
                            controller.setEyes(customColorValue)
                        }
                    }
                }

                LabeledContent("Blinking") {
                    HStack {
                        Button("Blink Now", systemImage: "eyes") {
                            controller.blink()
                        }
                        if controller.isIdleBlinking {
                            Button("Stop Periodic", systemImage: "stop.fill", role: .destructive) {
                                controller.stopIdleBlinking()
                            }
                        } else {
                            Button("Start Periodic", systemImage: "clock.arrow.trianglehead.counterclockwise.rotate.90") {
                                controller.startIdleBlinking(color: customColorValue)
                            }
                        }
                    }
                }

                HStack {
                    Spacer()
                    Button("Turn Eyes Off", systemImage: "power") {
                        controller.setEyes("off")
                    }
                }
            }
            .buttonStyle(.bordered)
            .disabled(controller.isBusy || !controller.status.eyes)
            .padding(.top, 6)
        }
    }

    private var cameraPanel: some View {
        GroupBox("Camera") {
            VStack {
                if let cameraImage = controller.cameraImage {
                    Image(nsImage: cameraImage)
                        .resizable()
                        .scaledToFit()
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .accessibilityLabel("Latest image from Karl’s camera")
                } else {
                    ContentUnavailableView(
                        "No Camera Image",
                        systemImage: "camera",
                        description: Text("Capture a still image to see Karl’s view.")
                    )
                    .frame(minHeight: 280)
                }
                Button("Capture Image", systemImage: "camera.fill") {
                    controller.captureCamera()
                }
                .buttonStyle(.borderedProminent)
                .disabled(controller.isBusy || !controller.status.camera)
            }
            .padding(.top, 6)
        }
        .frame(minWidth: 360)
    }

    private func speak() {
        controller.speak(speechText)
    }

    private var customColorValue: String {
        guard let color = NSColor(customEyeColor).usingColorSpace(.deviceRGB) else {
            return "0,80,255"
        }
        let red = Int((color.redComponent * 255).rounded())
        let green = Int((color.greenComponent * 255).rounded())
        let blue = Int((color.blueComponent * 255).rounded())
        return "\(red),\(green),\(blue)"
    }
}
