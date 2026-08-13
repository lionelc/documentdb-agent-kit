FROM documentdb-orders-base:latest

ENV SDK="python"

# Bake the reference implementation in. solve.sh copies it into /app when the
# oracle runs. The agent under evaluation never sees /reference.
COPY reference /reference

# Pre-install the reference impl's dependencies so the oracle runs quickly and,
# more importantly, so build.sh works with no internet access during grading.
RUN pip3 install --no-cache-dir --break-system-packages -r /reference/requirements.txt

WORKDIR /app
