# Marker file — makes /app/backend/tests a Python package so the
# tests can share a small `_test_creds` fixture module via relative
# import. Without this, collection fails with "attempted relative
# import with no known parent package".
