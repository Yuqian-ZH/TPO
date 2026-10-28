"""Run the requested scan without ever printing matching credential material."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    # Capture the exact requested grep pipeline; never emit its potentially secret output.
    command = r'''grep -rnE "sk-[A-Za-z0-9]{8,}" ~/task1 ~/TPO 2>/dev/null | grep -v "sk-\.\.\." | head'''
    scan = subprocess.run(['bash', '-c', command], capture_output=True)
    matches = scan.stdout.decode(errors='replace').splitlines()
    key = os.environ.get('DASHSCOPE_API_KEY', '').encode()
    assert key, 'Source the credential environment before running the scan'
    exact_key_matches = []
    for directory in [ROOT, ROOT.parent / 'TPO']:
        for path in directory.rglob('*'):
            if path.is_file() and not path.is_symlink():
                if key in path.read_bytes():
                    exact_key_matches.append(str(path))
    result = {'requested_grep_output_empty': not matches,
              'requested_grep_match_lines_capped_at_10': len(matches),
              'exact_current_credential_value_matches': len(exact_key_matches),
              'status': 'PASS' if not matches and not exact_key_matches else 'FAIL',
              'note': 'Matching text and credential values are never emitted or saved. External credential file is outside the scanned project roots.'}
    if matches:
        result['regex_matching_locations_redacted'] = [':'.join(line.split(':')[:2]) for line in matches]
    if exact_key_matches:
        result['exact_key_matching_files_redacted'] = exact_key_matches
    (ROOT / 'secret_scan_result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'SECRET_SCAN_{result["status"]}: requested grep output '
          f'{"empty" if not matches else "contained redacted matches"}; '
          f'exact credential matches {len(exact_key_matches)}.')
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
