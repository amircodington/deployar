# What Liara builds (decision 16): the full image is built by GitHub Actions (.github/workflows/image.yml from
# deploy/Dockerfile) because Liara's basic bundle stops a build after 5 minutes. Pulling it takes seconds.
# The tag is the commit CI built; CI rewrites this line (Liara never re-pulls a moving tag like :latest).
FROM ghcr.io/amircodington/deployar:beb2be1540996c210a6e25ad6d78676d981d6b2d
EXPOSE 3000
