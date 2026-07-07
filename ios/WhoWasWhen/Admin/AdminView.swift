import SwiftUI

/// Admin-build settings tab: holds the service-account key (Keychain only)
/// and a connection test. The key is the same JSON the sheet-maintenance
/// scripts use; paste it once.
struct AdminView: View {
    @State private var pastedJSON: String = ""
    @State private var configuredEmail: String? = AdminCredentials.load()?.clientEmail
    @State private var status: String?

    var body: some View {
        NavigationStack {
            Form {
                if let email = configuredEmail {
                    Section("Service account") {
                        LabeledContent("Signed in as") { Text(email).font(.footnote) }
                        Button("Test connection") { test() }
                        Button("Remove key", role: .destructive) {
                            AdminCredentials.delete()
                            configuredEmail = nil
                            status = nil
                        }
                    }
                } else {
                    Section("Service account key") {
                        TextField("Paste the service-account JSON here",
                                  text: $pastedJSON, axis: .vertical)
                            .lineLimit(6...12)
                            .font(.footnote.monospaced())
                            .autocorrectionDisabled()
                            .textInputAutocapitalization(.never)
                        Button("Save to Keychain") {
                            if AdminCredentials.save(json: Data(pastedJSON.utf8)) {
                                configuredEmail = AdminCredentials.load()?.clientEmail
                                pastedJSON = ""
                                status = nil
                            } else {
                                status = "That doesn't look like a service-account JSON key."
                            }
                        }
                        .disabled(pastedJSON.isEmpty)
                    }
                }
                if let status {
                    Section { Text(status).font(.footnote).foregroundStyle(.secondary) }
                }
                Section {
                    Text("Corrections queue: edits, event deletions, and notes land "
                         + "on the sheet's Corrections tab — review and apply at the "
                         + "desk with apply_corrections.py.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Admin")
        }
    }

    private func test() {
        guard let creds = AdminCredentials.load() else { return }
        status = "Testing…"
        Task {
            do {
                try await SheetsClient(credentials: creds).testConnection()
                status = "Connected ✓ — sheet reachable, token valid."
            } catch {
                status = "Failed: \(error.localizedDescription)"
            }
        }
    }
}
