import Foundation

nonisolated struct HeadPose: Codable, Sendable {
    var x = 0.0
    var y = 0.0
    var z = 0.0
    var roll = 0.0
    var pitch = 0.0
    var yaw = 0.0
}

private nonisolated struct GotoRequest: Encodable, Sendable {
    let headPose: HeadPose?
    let antennas: [Double]?
    let bodyYaw: Double?
    let duration: Double
    let interpolation = "minjerk"

    enum CodingKeys: String, CodingKey {
        case headPose = "head_pose"
        case antennas
        case bodyYaw = "body_yaw"
        case duration
        case interpolation
    }
}

private nonisolated struct TrackingRequest: Encodable, Sendable {
    let weight: Double
}

actor DaemonClient {
    private let baseURL = URL(string: "http://127.0.0.1:8000")

    func wake() async throws {
        try await post(path: "/api/move/play/wake_up")
    }

    func goto(
        head: HeadPose? = nil,
        antennas: [Double]? = nil,
        bodyYaw: Double? = nil,
        duration: Double = 0.6
    ) async throws {
        try await post(path: "/api/motors/set_mode/enabled")
        let request = GotoRequest(
            headPose: head,
            antennas: antennas,
            bodyYaw: bodyYaw,
            duration: duration
        )
        try await post(path: "/api/move/goto", body: request)
        try await Task.sleep(for: .seconds(duration + 0.1))
    }

    func setFaceTracking(enabled: Bool, weight: Double = 0.35) async throws {
        if enabled {
            try await post(
                path: "/api/media/tracking/enable",
                body: TrackingRequest(weight: weight)
            )
        } else {
            try await post(path: "/api/media/tracking/disable")
        }
    }

    func playEmotion(_ name: String) async throws {
        guard let url = URL(
            string: "http://127.0.0.1:8000/api/move/play/recorded-move-dataset/"
                + "pollen-robotics%2Freachy-mini-emotions-library/\(name)"
        ) else {
            throw DaemonClientError.invalidURL(name)
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        try await send(request)
    }

    private func post(path: String) async throws {
        guard let url = baseURL?.appending(path: path) else {
            throw DaemonClientError.invalidURL(path)
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        try await send(request)
    }

    private func post<Body: Encodable & Sendable>(
        path: String,
        body: Body
    ) async throws {
        guard let url = baseURL?.appending(path: path) else {
            throw DaemonClientError.invalidURL(path)
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        try await send(request)
    }

    private func send(_ request: URLRequest) async throws {
        let (_, response) = try await URLSession.shared.data(for: request)
        guard let response = response as? HTTPURLResponse,
              (200..<300).contains(response.statusCode) else {
            throw DaemonClientError.requestFailed(
                (response as? HTTPURLResponse)?.statusCode
            )
        }
    }
}

nonisolated enum DaemonClientError: LocalizedError {
    case invalidURL(String)
    case requestFailed(Int?)

    var errorDescription: String? {
        switch self {
        case .invalidURL(let path):
            "Invalid daemon URL for \(path)."
        case .requestFailed(let statusCode):
            if let statusCode {
                "The Reachy daemon returned HTTP \(statusCode)."
            } else {
                "The Reachy daemon did not return an HTTP response."
            }
        }
    }
}
