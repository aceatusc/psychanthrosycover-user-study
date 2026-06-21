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
// Columns: timestamp | participant_id | session_id | submitted_at | pair_key | conv_a_file | choice

function doPost(e) {
  try {
    Logger.log('doPost called');
    Logger.log('postData: ' + JSON.stringify(e.postData));

    const raw = e.postData && e.postData.contents;
    if (!raw) {
      Logger.log('ERROR: empty postData.contents');
      throw new Error('No POST body received');
    }

    const data = JSON.parse(raw);
    Logger.log('parsed data: ' + JSON.stringify(data));

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    if (!ss) throw new Error('Could not open spreadsheet — run from a Sheet-bound script');
    const sheet = ss.getActiveSheet();

    if (sheet.getLastRow() === 0) {
      sheet.appendRow(['timestamp', 'participant_id', 'session_id', 'submitted_at', 'pair_key', 'conv_a_file', 'choice']);
    }

    const ts = new Date().toISOString();
    for (const r of data.responses) {
      sheet.appendRow([ts, data.participant_id, data.session_id, data.submitted_at, r.pair_key, r.conv_a_file, r.choice]);
    }

    Logger.log('wrote ' + data.responses.length + ' rows');
    return ContentService.createTextOutput(JSON.stringify({ ok: true })).setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    Logger.log('EXCEPTION: ' + err.message);
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: err.message })).setMimeType(ContentService.MimeType.JSON);
  }
}

// Diagnostic GET — open the deployment URL in a browser to verify the script + sheet are wired up.
function doGet() {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss ? ss.getActiveSheet() : null;
    const info = sheet
      ? 'Sheet: "' + sheet.getName() + '" in "' + ss.getName() + '" — rows: ' + sheet.getLastRow()
      : 'WARNING: no active spreadsheet found';
    return ContentService.createTextOutput('Study backend is running.\n' + info);
  } catch (err) {
    return ContentService.createTextOutput('Study backend running but sheet error: ' + err.message);
  }
}
