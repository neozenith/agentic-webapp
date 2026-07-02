// plotly.js-dist-min ships no type declarations; react-plotly.js's factory only needs the
// bundle as an opaque object, so an ambient default-export is sufficient here.
declare module "plotly.js-dist-min" {
  const Plotly: object;
  export default Plotly;
}
