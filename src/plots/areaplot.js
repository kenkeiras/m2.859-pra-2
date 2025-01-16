const render_query_areaplot = async (db, query, params, view) => {
    const svg = view.svg;
    const margin = view.margin;
    return db.query(query, params).then((result) => {
        // Clear svg
        svg._groups.map(i => i.map(j => j.innerHTML = ''));

        const data = result.data.results[0];
        const values = data.values;

        const testbar = document.getElementById('testbar');

        const width = document.body.clientWidth - margin.left - margin.right;
        const height = document.body.clientHeight - margin.top - margin.bottom - testbar.clientHeight;

        // Add X axis
        const x = d3.scaleLinear()
              .domain([Math.min(...values.map(v => v[0])),
                       Math.max(...values.map(v => v[0]))])
              .range([ 0, width ]);

        svg.append("g")
            .attr("transform", "translate(0," + height + ")")
            .call(d3.axisBottom(x))
            .selectAll("text")
            .style("text-anchor", "end")
            .attr("transform", "rotate(-25)")
        ;

        // Add Y axis
        var y = d3.scaleLinear()
            .domain([Math.min(...values.map(v => v[1])),
                     Math.max(...values.map(v => v[1]))])
            .range([ height, 0]);
        svg.append("g")
            .call(d3.axisLeft(y));

        // Add dots
        svg.append('path')
            .datum(values)
            .attr("fill", "#cce5df")
            .attr("stroke", "#69b3a2")
            .attr("stroke-width", 1.5)
            .attr("d", d3.area()
                  .x(function(d) { return x(d[0]) })
                  .y0(y(0))
                  .y1(function(d) { return y(d[1]) })
                 )
    });
};
