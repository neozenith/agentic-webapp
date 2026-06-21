{#
  dbt >=1.8 only resolves the `test` materialization from the root project or
  dbt-core, NOT from installed packages. Elementary ships its own `test`
  materialization (it captures test results), so without this re-export the
  package's version is ignored and elementary_test_results never populate.

  Re-export elementary's materialization from the root project so dbt picks it
  up. This is the documented elementary fix for dbt >=1.8.
#}
{% materialization test, default %}
  {{ return(elementary.materialization_test_default()) }}
{% endmaterialization %}
