import Foundation
import Security

/// The Google service-account credentials the admin build uses to append
/// corrections to the master sheet. Pasted once (the same JSON key the
/// sheet-maintenance scripts use), stored only in the Keychain — never in
/// the binary, the repo, or UserDefaults.
struct AdminCredentials: Sendable {
    let clientEmail: String
    let privateKeyPEM: String

    private static let service = "com.giovannicoppola.WhoWasWhen.admin"
    private static let account = "service-account-json"

    static func parse(json: Data) -> AdminCredentials? {
        guard let obj = try? JSONSerialization.jsonObject(with: json) as? [String: Any],
              let email = obj["client_email"] as? String,
              let key = obj["private_key"] as? String,
              key.contains("BEGIN PRIVATE KEY") else { return nil }
        return AdminCredentials(clientEmail: email, privateKeyPEM: key)
    }

    // MARK: - Keychain

    static func save(json: Data) -> Bool {
        guard parse(json: json) != nil else { return false }
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
        var add = query
        add[kSecValueData as String] = json
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        return SecItemAdd(add as CFDictionary, nil) == errSecSuccess
    }

    static func load() -> AdminCredentials? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
        ]
        var out: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &out) == errSecSuccess,
              let data = out as? Data else { return nil }
        return parse(json: data)
    }

    static func delete() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
    }
}
