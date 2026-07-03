import SwiftUI

/// Admin-build capture UI, presented from a result's detail view: edit one
/// field, delete a duplicate event, or jot a note — each appends a row to
/// the sheet's Corrections queue for desk-side review.
struct CurationSheet: View {
    let result: SearchResult
    @Environment(\.dismiss) private var dismiss
    @Environment(AppModel.self) private var app

    @State private var record: RawRecord?
    @State private var selectedField: String = ""
    @State private var newValue: String = ""
    @State private var noteText: String = ""
    @State private var confirmDelete = false
    @State private var status: String?
    @State private var busy = false

    private var currentValue: String {
        record?.fields.first { $0.name == selectedField }?.value ?? ""
    }

    var body: some View {
        NavigationStack {
            Form {
                if AdminCredentials.load() == nil {
                    Label("Paste the service-account key in the Admin tab first.",
                          systemImage: "key.slash")
                        .foregroundStyle(.orange)
                } else if let record {
                    Section("Edit \(record.tab == "Rulers" ? "person" : "event")") {
                        Picker("Field", selection: $selectedField) {
                            ForEach(record.fields) { f in Text(f.name).tag(f.name) }
                        }
                        LabeledContent("Current") {
                            Text(currentValue.isEmpty ? "—" : currentValue)
                                .multilineTextAlignment(.trailing)
                        }
                        TextField("New value", text: $newValue, axis: .vertical)
                        Button("Submit edit") {
                            submit(Correction.edit(tab: record.tab, key: record.key,
                                                   field: selectedField,
                                                   snapshot: currentValue,
                                                   proposed: newValue))
                        }
                        .disabled(busy || newValue == currentValue)
                    }

                    Section("Note to self") {
                        TextField("About this record…", text: $noteText, axis: .vertical)
                        Button("Submit note") {
                            submit(Correction.note(tab: record.tab, key: record.key,
                                                   text: noteText))
                        }
                        .disabled(busy || noteText.isEmpty)
                    }

                    if record.tab == "Events" {
                        Section {
                            Button("Delete this event (duplicate)", role: .destructive) {
                                confirmDelete = true
                            }
                            .disabled(busy)
                            .confirmationDialog("Queue deletion of \(record.displayName)?",
                                                isPresented: $confirmDelete,
                                                titleVisibility: .visible) {
                                Button("Queue deletion", role: .destructive) {
                                    submit(Correction.deleteEvent(key: record.key,
                                                                  name: record.displayName))
                                }
                            }
                        }
                    }

                    if let status {
                        Section { Text(status).font(.footnote).foregroundStyle(.secondary) }
                    }
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("Curate")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } }
            }
            .task { await loadRecord() }
            .onChange(of: selectedField) { newValue = currentValue }
        }
    }

    private func loadRecord() async {
        if result.kind == .ruler, let id = result.rulerID {
            record = await app.rulerRawFields(byID: id)
        } else if let id = result.eventID {
            record = await app.eventRawFields(byID: id)
        }
        if let first = record?.fields.first {
            selectedField = first.name
            newValue = first.value
        }
    }

    private func submit(_ row: [String]) {
        guard let creds = AdminCredentials.load() else { return }
        busy = true
        status = nil
        Task {
            do {
                try await SheetsClient(credentials: creds).appendCorrection(row)
                status = "Queued ✓ — review with apply_corrections.py"
                noteText = ""
            } catch {
                status = "Failed: \(error.localizedDescription)"
            }
            busy = false
        }
    }
}
