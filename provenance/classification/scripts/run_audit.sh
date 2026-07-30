#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /path/to/c-12-6-3.pdf" >&2
  exit 2
fi

audit_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
audit_root="$(cd -- "${audit_script_dir}/.." && pwd)"
paper_pdf="$(cd -- "$(dirname -- "$1")" && pwd)/$(basename -- "$1")"
expected_pdf_sha256="6da3d15935e5eb8eca9e533c60ffb08db48cb335a94f88c007bd449729f8cf79"
actual_pdf_sha256="$(sha256sum -- "${paper_pdf}" | awk '{print $1}')"

if [[ "${actual_pdf_sha256}" != "${expected_pdf_sha256}" ]]; then
  echo "primary PDF SHA-256 mismatch" >&2
  echo "expected ${expected_pdf_sha256}" >&2
  echo "actual   ${actual_pdf_sha256}" >&2
  exit 1
fi

mkdir -p "${audit_root}/build"

python3 "${audit_root}/scripts/extract_paper_templates.py" \
  --pdf "${paper_pdf}" \
  --source "${audit_root}/upstream/link_extension.py" \
  --output-dir "${audit_root}/build"

python3 "${audit_root}/scripts/build_classification_provenance.py" \
  --pdf "${paper_pdf}" \
  --paper-templates "${audit_root}/build/paper.templates.json" \
  --template-comparison \
    "${audit_root}/build/paper-template-comparison.audit.json" \
  --catalog-input "${audit_root}/upstream/catalog-input.json" \
  --catalog-audit "${audit_root}/upstream/catalog.audit.manifest.json" \
  --independent-audit \
    "${audit_root}/upstream/catalog.independent-audit.json" \
  --numbering-manifest "${audit_root}/upstream/numbering.manifest.json" \
  --bundle-numbering-audit \
    "${audit_root}/upstream/bundle-numbering.audit.json" \
  --output-dir "${audit_root}/build"

for audit_name in \
  paper.templates.json \
  paper-template-comparison.audit.json \
  classification-provenance.audit.json \
  literature-to-project-class-map.json
do
  cmp "${audit_root}/audit/${audit_name}" "${audit_root}/build/${audit_name}"
done

echo "audit reproduction PASS"
