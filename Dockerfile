# What Liara builds (decision 16): the full image is built by GitHub Actions (.github/workflows/image.yml from
# deploy/Dockerfile) because Liara's basic bundle stops a build after 5 minutes. Pulling it takes seconds.
# The tag is the commit CI built; CI rewrites this line (Liara never re-pulls a moving tag like :latest).
FROM ghcr.io/amircodington/deployar:9f58e5ca800f477c8462c31829b360e0cad6462b
EXPOSE 3000
