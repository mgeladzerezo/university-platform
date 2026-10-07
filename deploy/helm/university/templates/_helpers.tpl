{{- define "university.labels" -}}
app.kubernetes.io/name: university
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "university.selectorLabels" -}}
app.kubernetes.io/name: university
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{- define "university.image" -}}
{{ .root.Values.image.registry }}/{{ .name }}:{{ required "image.tag is required" .root.Values.image.tag }}
{{- end }}

{{/* Environment of every backend container: ConfigMap plus the synced Secret. */}}
{{- define "university.backendEnv" -}}
envFrom:
  - configMapRef:
      name: {{ .Release.Name }}-config
  - secretRef:
      name: {{ .Release.Name }}-secrets
{{- end }}

{{- define "university.podSecurityContext" -}}
runAsNonRoot: true
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{- define "university.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end }}

{{/* Egress rules shared by api, worker, beat and the migration job. */}}
{{- define "university.backendEgress" -}}
# PostgreSQL and Redis in the VPC database subnets
- to:
    - ipBlock:
        cidr: {{ .Values.networkPolicy.vpcCidr }}
  ports:
    - { protocol: TCP, port: 5432 }
    - { protocol: TCP, port: 6379 }
# HTTPS to AWS APIs (S3, SES), Keycloak and the Anthropic API. Plain
# NetworkPolicy cannot filter by host name; that needs an egress proxy or a CNI
# with FQDN policies.
- to:
    - ipBlock:
        cidr: 0.0.0.0/0
  ports:
    - { protocol: TCP, port: 443 }
# EKS Pod Identity agent (link-local address on the node)
- to:
    - ipBlock:
        cidr: 169.254.170.23/32
  ports:
    - { protocol: TCP, port: 80 }
# ClamAV daemon
- to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: {{ .Values.networkPolicy.clamavNamespace }}
  ports:
    - { protocol: TCP, port: 3310 }
{{- end }}
