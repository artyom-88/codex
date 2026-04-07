typeset -gr _CODEX_SIGNOZ_PROJECT_ATTR_HELPER="${${(%):-%N}:A:h}/project_resource_attrs.py"

_codex_sync_project_otel_resource_attrs() {
  local updated

  [[ -f "$_CODEX_SIGNOZ_PROJECT_ATTR_HELPER" ]] || return 0
  updated="$(python3 "$_CODEX_SIGNOZ_PROJECT_ATTR_HELPER" --cwd "$PWD" --existing "${OTEL_RESOURCE_ATTRIBUTES-}" 2>/dev/null)" || return 0

  if [[ -n "$updated" ]]; then
    export OTEL_RESOURCE_ATTRIBUTES="$updated"
  else
    unset OTEL_RESOURCE_ATTRIBUTES
  fi
}

autoload -Uz add-zsh-hook
add-zsh-hook -d chpwd _codex_sync_project_otel_resource_attrs 2>/dev/null
add-zsh-hook chpwd _codex_sync_project_otel_resource_attrs
_codex_sync_project_otel_resource_attrs
