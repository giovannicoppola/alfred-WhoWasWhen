import Foundation
import Security

/// Minimal Google Sheets client for the admin build: service-account JWT
/// (RS256 via Security.framework, no dependencies) exchanged for an access
/// token, used to append rows to the Corrections tab.
actor SheetsClient {
    enum ClientError: LocalizedError {
        case badKey, signingFailed, tokenFailed(String), appendFailed(String)
        var errorDescription: String? {
            switch self {
            case .badKey: "The private key could not be read."
            case .signingFailed: "Signing the request failed."
            case .tokenFailed(let m): "Google sign-in failed: \(m)"
            case .appendFailed(let m): "Appending to the sheet failed: \(m)"
            }
        }
    }

    static let spreadsheetID = "1GKI1744hxSBmB75CrIYssK6Y8-Hd48kpaggvOG1kUM8"
    private let credentials: AdminCredentials
    private var cachedToken: (value: String, expiry: Date)?

    init(credentials: AdminCredentials) {
        self.credentials = credentials
    }

    /// Appends one row to the Corrections tab.
    func appendCorrection(_ row: [String]) async throws {
        let token = try await accessToken()
        var req = URLRequest(url: URL(string:
            "https://sheets.googleapis.com/v4/spreadsheets/\(Self.spreadsheetID)/values/"
            + "Corrections!A1:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS")!)
        req.httpMethod = "POST"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONSerialization.data(withJSONObject: ["values": [row]])
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard (resp as? HTTPURLResponse)?.statusCode == 200 else {
            throw ClientError.appendFailed(String(data: data, encoding: .utf8) ?? "?")
        }
    }

    /// Sanity check used by the settings screen's Test button.
    func testConnection() async throws {
        let token = try await accessToken()
        var req = URLRequest(url: URL(string:
            "https://sheets.googleapis.com/v4/spreadsheets/\(Self.spreadsheetID)"
            + "?fields=properties.title")!)
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard (resp as? HTTPURLResponse)?.statusCode == 200 else {
            throw ClientError.appendFailed(String(data: data, encoding: .utf8) ?? "?")
        }
    }

    // MARK: - OAuth (service-account JWT bearer)

    private func accessToken() async throws -> String {
        if let t = cachedToken, t.expiry > Date().addingTimeInterval(60) {
            return t.value
        }
        let assertion = try signedJWT()
        var req = URLRequest(url: URL(string: "https://oauth2.googleapis.com/token")!)
        req.httpMethod = "POST"
        req.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        req.httpBody = ("grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer"
                        + "&assertion=\(assertion)").data(using: .utf8)
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard (resp as? HTTPURLResponse)?.statusCode == 200,
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let token = obj["access_token"] as? String else {
            throw ClientError.tokenFailed(String(data: data, encoding: .utf8) ?? "?")
        }
        cachedToken = (token, Date().addingTimeInterval(3300))
        return token
    }

    private func signedJWT() throws -> String {
        let now = Int(Date().timeIntervalSince1970)
        let header = #"{"alg":"RS256","typ":"JWT"}"#
        let claims = """
            {"iss":"\(credentials.clientEmail)",\
            "scope":"https://www.googleapis.com/auth/spreadsheets",\
            "aud":"https://oauth2.googleapis.com/token",\
            "iat":\(now),"exp":\(now + 3600)}
            """
        let signingInput = base64url(Data(header.utf8)) + "." + base64url(Data(claims.utf8))
        let signature = try sign(Data(signingInput.utf8))
        return signingInput + "." + base64url(signature)
    }

    private func sign(_ message: Data) throws -> Data {
        guard let key = Self.privateKey(fromPEM: credentials.privateKeyPEM) else {
            throw ClientError.badKey
        }
        var error: Unmanaged<CFError>?
        guard let sig = SecKeyCreateSignature(
            key, .rsaSignatureMessagePKCS1v15SHA256, message as CFData, &error) else {
            throw ClientError.signingFailed
        }
        return sig as Data
    }

    /// Google keys are PKCS#8 PEM; Security wants raw PKCS#1 for RSA. The
    /// 2048-bit RSA PKCS#8 wrapper is a fixed 26-byte prefix — strip it,
    /// falling back to the untouched bytes just in case.
    private static func privateKey(fromPEM pem: String) -> SecKey? {
        let body = pem
            .replacingOccurrences(of: "-----BEGIN PRIVATE KEY-----", with: "")
            .replacingOccurrences(of: "-----END PRIVATE KEY-----", with: "")
            .replacingOccurrences(of: "\n", with: "")
            .replacingOccurrences(of: "\\n", with: "")
        guard let der = Data(base64Encoded: body) else { return nil }
        let attrs: [String: Any] = [
            kSecAttrKeyType as String: kSecAttrKeyTypeRSA,
            kSecAttrKeyClass as String: kSecAttrKeyClassPrivate,
        ]
        for candidate in [der.dropFirst(26), der[...]] {
            if let key = SecKeyCreateWithData(Data(candidate) as CFData,
                                              attrs as CFDictionary, nil) {
                return key
            }
        }
        return nil
    }

    private func base64url(_ data: Data) -> String {
        data.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}

/// Builders for the Corrections queue rows (schema shared with
/// sheet-maintenance/apply_corrections.py).
enum Correction {
    static func timestamp() -> String {
        ISO8601DateFormatter().string(from: Date())
    }

    static func edit(tab: String, key: String, field: String,
                     snapshot: String, proposed: String) -> [String] {
        [timestamp(), "edit", tab, key, field, snapshot, proposed, "", "pending", ""]
    }

    static func deleteEvent(key: String, name: String) -> [String] {
        [timestamp(), "delete-event", "Events", key, "", name, "", "", "pending", ""]
    }

    static func note(tab: String, key: String, text: String) -> [String] {
        [timestamp(), "note", tab, key, "", "", "", text, "pending", ""]
    }
}
