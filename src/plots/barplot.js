const render_query_barplot = async (db, query, params, view) => {
    const svg = view.svg;
    const margin = view.margin;
    return db.query(query, params).then((result) => {
        // Clear svg
        svg._groups.map(i => i.map(j => j.innerHTML = ''));

        const data = result.data.results[0];
        const values = data.values;

        let xCol = 0;
        let countCol = 1;
        let stacked = false;
        if (data.columns.length == 3) {
            countCol = 2;
            stacked = true;
        }

        const testbar = document.getElementById('testbar');

        const width = document.body.clientWidth - margin.left - margin.right;
        const height = document.body.clientHeight - margin.top - margin.bottom - testbar.clientHeight;

        // Add X axis
        const x = d3.scaleBand()
              .range([ 0, width ])
              .domain(values.map(function(d) { return d[xCol]; }))
              .padding(0.2);

        svg.append("g")
            .attr("transform", "translate(0," + height + ")")
            .call(d3.axisBottom(x))
            .selectAll("text")
            .style("text-anchor", "end")
            .attr("transform", "rotate(-25)")
        ;

        if (!stacked) {

            // Add Y axis
            var y = d3.scaleLinear()
                .domain([0, Math.max(...values.map(v => v[countCol]))])
                .range([ height, 0]);
            svg.append("g")
                .call(d3.axisLeft(y));

            svg.selectAll('mybar')
                .data(values)
                .enter()
                .append("rect")
                .attr('x', function(d) {return x(d[xCol]);})
                .attr('y', function(d) {return y(d[countCol]);})
                .attr("width", x.bandwidth())
                .attr("height", function(d) { return height - y(d[countCol]); })
                .attr("fill", "#69b3a2");
        }
        else {
            let [stacks, keys] = stack(
                data.values,
                x => x[xCol],
                x => x[1],
                x => x[countCol]);

            console.log(JSON.parse(JSON.stringify(stacks)), keys);
            if (keys.map(v => ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"].indexOf(v) >= 0).every(v => v)) {
                // Severity keys
                keys = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"];
            }

             // color palette = one color per subgroup
            var color = d3.scaleOrdinal()
                .domain(keys)
                .range(['#00aa00', '#88bb00', '#bb8800', '#f7958a', '#e51600'])

            // Should all reach top?
            const percent_stack_plot = true;
            if (percent_stack_plot) {
                // Add Y axis
                var y = d3.scaleLinear()
                    .domain([0, 100])
                    .range([ height, 0 ]);
                svg.append("g")
                    .call(d3.axisLeft(y));

                stacks.forEach(function(d){
                    // Compute the total
                    let tot = 0;
                    for (const i in keys){ const name=keys[i] ; if (!!d[name]){ tot += +d[name] } }
                    // Now normalize
                    for (const i in keys){ const name=keys[i] ; if (!!d[name]){ d[name] = d[name] / tot * 100}}
                })
            }
            else {
                // Add Y axis
                var y = d3.scaleLinear()
                    .domain([0, Math.max(...values.map(v => v[countCol]))])
                    .range([ height, 0]);
                svg.append("g")
                    .call(d3.axisLeft(y));
            }

            //stack the data? --> stack per subgroup
            var stackedData = d3.stack()
                .keys(keys)
            (stacks);

            // Show the bars
            svg.append("g")
                .selectAll("g")
            // Enter in the stack data = loop key per key = group per group
                .data(stackedData)
                .enter().append("g")
                .attr("fill", function(d) { return color(d.key); })
                .selectAll("rect")
            // enter a second time = loop subgroup per subgroup to add all rectangles
                .data(function(d) { return d; })
                .enter().append("rect")
                .attr("x", function(d) { return x(d.data.__x__); })
                .attr("y", function(d) { if(isNaN(d[1])) {return y(d[0]);}; return y(d[1]); })
                .attr("height", function(d) { if(isNaN(d[1])) {return 0;} ; return y(d[0]) - y(d[1]); })
                .attr("width", x.bandwidth())
                // .attr("stroke", "grey")
                .on("mouseover", function(d){
                    var subgroupName = d3.select(this.parentNode).datum().key;
                    var subgroupValue = d.data[subgroupName];
                    console.log("name", subgroupName, "value", subgroupValue);
                })
        }
    });
};

function stack(data, get_x_key, get_stack_key, get_count) {
    // Collect keys
    const keysReader = {};
    for (const row of data) {
        const key = get_stack_key(row);
        if (key) {
            keysReader[key] = true;
        }
    }
    const keys = Object.keys(keysReader);

    const results = {};
    for (const row of data) {
        const xkey = get_x_key(row);
        const key = get_stack_key(row);
        if (results[xkey] === undefined) {
            const new_result = {"__x__": xkey};
            for (const k of keys) {
                new_result[k] = 0;
            }
            results[xkey] = new_result;
        }

        results[xkey][key] = get_count(row);
    }

    return [Object.values(results), keys];
}
