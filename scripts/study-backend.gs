// Google Apps Script backend for the annotation study.
//
// Setup (one-time):
//   1. Create a new Google Sheet (any name).
//   2. In the sheet: Extensions → Apps Script.
//   3. Delete the default code and paste this entire file.
//   4. Click Deploy → New deployment.
//      - Type: Web App
//      - Execute as: Me
//      - Who has access: Anyone
//   5. Authorize when prompted.
//   6. Copy the deployment URL.
//   7. Paste it into docs/assets/study.js as the value of SUBMIT_URL.
//
// Each submission writes one row per pair response to the active sheet.
// Columns: timestamp | participant_id | session_id | pair_key | conv_a_file | choice

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

    // Write header row if the sheet is empty
    if (sheet.getLastRow() === 0) {
      sheet.appendRow([
        'timestamp',
        'participant_id',
        'session_id',
        'submitted_at',
        'pair_key',
        'conv_a_file',
        'choice',
      ]);
    }

    const ts = new Date().toISOString();
    for (const r of data.responses) {
      sheet.appendRow([
        ts,
        data.participant_id,
        data.session_id,
        data.submitted_at,
        r.pair_key,
        r.conv_a_file,
        r.choice,
      ]);
    }

    return ContentService
      .createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, error: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Health check — GET https://<deployment-url>/exec
function doGet() {
  return ContentService.createTextOutput('Study backend is running.');
}
