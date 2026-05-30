const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { releaseChannel, isProductionRelease } = require('./release-utils');

const desktopRoot = path.resolve(__dirname, '..');
const distRoot = path.join(desktopRoot, 'dist');
const pkg = JSON.parse(fs.readFileSync(path.join(desktopRoot, 'package.json'), 'utf8'));

function fail(message) {
  console.error(`SIGNATURE_FAIL: ${message}`);
  process.exit(1);
}

function warn(message) {
  console.warn(`SIGNATURE_WARN: ${message}`);
}

function powershellSingleQuoted(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

function artifactPaths() {
  const version = pkg.version;
  return {
    installers: [
      path.join(distRoot, `Playro Setup ${version}.exe`),
      path.join(distRoot, `Playro ${version}.exe`),
    ],
    unpacked: path.join(distRoot, 'win-unpacked', 'Playro.exe'),
  };
}

function requiredArtifacts() {
  const artifacts = artifactPaths();
  const existingInstallers = artifacts.installers.filter((filePath) => fs.existsSync(filePath));
  const missingInstallers = artifacts.installers.filter((filePath) => !fs.existsSync(filePath));

  if (missingInstallers.length) {
    fail(`Missing Windows installer artifact(s): ${missingInstallers.join(', ')}`);
  }

  const files = [...existingInstallers];
  if (fs.existsSync(artifacts.unpacked)) {
    files.push(artifacts.unpacked);
  } else if (isProductionRelease()) {
    fail(`Missing unpacked Windows executable: ${artifacts.unpacked}`);
  } else {
    warn(
      'dist\\win-unpacked\\Playro.exe is not present. ' +
      `Non-production channel (${releaseChannel()}) will verify installer/portable artifacts only.`
    );
  }

  return files;
}

function powershellSignature(filePath) {
  const command = [
    '$ErrorActionPreference = "Stop"',
    `$sig = Get-AuthenticodeSignature -FilePath ${powershellSingleQuoted(filePath)}`,
    '$obj = [pscustomobject]@{',
    '  Status = [string]$sig.Status',
    '  Subject = if ($sig.SignerCertificate) { [string]$sig.SignerCertificate.Subject } else { "" }',
    '  Issuer = if ($sig.SignerCertificate) { [string]$sig.SignerCertificate.Issuer } else { "" }',
    '  Thumbprint = if ($sig.SignerCertificate) { [string]$sig.SignerCertificate.Thumbprint } else { "" }',
    '  File = [string]$sig.Path',
    '}',
    '$obj | ConvertTo-Json -Compress',
  ].join('\n');

  const output = execFileSync('powershell', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command], {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  }).trim();
  return JSON.parse(output);
}

function verifyOnWindows(filesToVerify) {
  return filesToVerify.map((filePath) => {
    const signature = powershellSignature(filePath);
    const relative = path.relative(desktopRoot, filePath);
    if (signature.Status !== 'Valid') {
      const status = signature.Status || 'Unknown';
      if (isProductionRelease()) {
        fail(`${relative} is not signed with a valid Authenticode signature (status=${status}).`);
      }
      warn(
        `${relative} has status=${status}. ` +
        `Non-production channel (${releaseChannel()}) allows unsigned artifacts.`
      );
    }
    return { file: relative, ...signature };
  });
}

function main() {
  const filesToVerify = requiredArtifacts();

  if (process.platform !== 'win32') {
    const message = 'Authenticode verification must run on Windows with PowerShell Get-AuthenticodeSignature.';
    if (isProductionRelease()) fail(message);
    warn(`${message} Current channel=${releaseChannel()}; treating as internal/test only.`);
    return;
  }

  const signatures = verifyOnWindows(filesToVerify);
  const allValid = signatures.every((signature) => signature.Status === 'Valid');
  if (allValid) {
    console.log('SIGNATURE_OK: Windows artifacts are signed and valid.');
  } else {
    console.log(`SIGNATURE_WARN: Signature checks completed for channel=${releaseChannel()} with unsigned/non-production warnings.`);
  }
  signatures.forEach((signature) => {
    console.log(`${signature.file}: ${signature.Subject || 'unknown subject'} (${signature.Thumbprint || 'no thumbprint'})`);
  });
}

main();