-- Runs once, on first start of an empty Postgres volume.
-- The test suite uses this database so it never touches your demo data.
CREATE DATABASE dealflow_test;
