# Apply secrets and configmaps from .env file
local_resource(
    'apply-secrets',
    cmd='./scripts/apply-secrets.sh',
    deps=['.env'],
    labels=['config']
)

k8s_yaml(
    [
        'k8s/auth-service.yaml',
        'k8s/traefik-middleware.yaml',
        'k8s/ingress-traefik.yaml'

    ]
)

docker_build('ghcr.io/trofkm/acl-auth-service:latest', 'auth_service')
k8s_resource('auth-service', port_forwards='8000', resource_deps=['apply-secrets'])
allow_k8s_contexts('default')
