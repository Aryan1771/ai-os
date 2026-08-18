#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo bash scripts/security_baseline.sh" >&2
  exit 1
fi

ufw --force reset
ufw default deny incoming
ufw default deny outgoing
ufw allow out to 127.0.0.1
ufw allow out 53
ufw allow out 80/tcp
ufw allow out 443/tcp
ufw --force enable

freshclam || true
systemctl enable --now clamav-daemon || true
systemctl enable --now apparmor

install -D -m 0644 security/apparmor.ai-os /etc/apparmor.d/ai-os
apparmor_parser -r /etc/apparmor.d/ai-os || true

ufw status verbose
echo "Security baseline applied. Domain-level API policy is enforced by the Python broker, not UFW."

