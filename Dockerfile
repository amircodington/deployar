# What Liara builds (decision 16): the full image is built by GitHub Actions (.github/workflows/image.yml from
# deploy/Dockerfile) because Liara's basic bundle stops a build after 5 minutes. Pulling it takes seconds.
# The tag is the commit CI built; CI rewrites this line (Liara never re-pulls a moving tag like :latest).
FROM ghcr.io/amircodington/deployar:7286984ce29503f51a45adf2db6bb4925491c6e9
EXPOSE 3000
