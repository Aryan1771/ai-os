# Repository Layout

The layout takes inspiration from distribution projects with a clear installer, configuration, branding, documentation, and package boundary. It remains an AI interface layer rather than a fork of another project.

```text
ai_os/       Runtime Python package
config/      Versioned, non-secret templates
install/     User-invoked Arch installation entry points
scripts/     Focused maintenance and security scripts
systemd/     Tracked service templates
security/    Tracked security policy templates
branding/    Original product assets only
archiso/     Additions for a copied Archiso profile
docs/        Authoritative installation and operation guides
tests/       Portable Python tests
```

Runtime state never belongs in this tree: `~/.ai_os`, local models, Chroma data, logs, user services, API tokens, and downloaded assets remain local to the Arch installation.
