{{- define "fineract.name" -}}
fineract
{{- end -}}

{{- define "fineract.labels" -}}
app.kubernetes.io/name: {{ include "fineract.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
