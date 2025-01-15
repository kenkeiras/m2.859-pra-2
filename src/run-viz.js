const load_db = async () => {
    const worker = new Worker('./sqljs/v1.12.0/worker.sql-wasm.js')
    const sqlPromise = initSqlJs({
        locateFile: file => `./sqljs/v1.12.0/${file}`
    });
    const dataPromise = fetch(
        "../data/nist/db.sqlite",
        {cache: "force-cache"},
    ).then(res => res.arrayBuffer());
    const [SQL, buf] = await Promise.all([sqlPromise, dataPromise])

    let next_id = 1;
    let listeners = {};
    let queryTimes = {};

    const dbConnection = {
        query: (query, params) => {
            const action_id = next_id++;
            queryTimes[action_id] = new Date();
            const prom = new Promise((resolve) => {
                listeners[action_id] = [resolve];
                worker.postMessage({
                    id: action_id,
                    action: "exec",
                    sql: query,
                    params: params || {}
                });
            });
            return prom;
        },
        onmessage: (event) => {
            console.debug("Message:", event);
            if (queryTimes[event.data.id]) {
                console.log("Query", event.data.id, "completed in",
                            (new Date()) - (queryTimes[event.data.id]));
                delete queryTimes[event.data.id];
            }
            if (listeners[event.data.id]) {
                for (const listener of listeners[event.data.id]) {
                    try {
                        listener(event);
                    }
                    catch(err) {
                        console.error(err);
                    }
                }
                delete listeners[event.data.id];
            }
        }
    };

    worker.onmessage = dbConnection.onmessage;

    // Open the file
    worker.postMessage({
        id: next_id++,
        action:"open",
        buffer: buf,
    });

    return dbConnection;
}

const render_query_barplot = async (db, query, params, view) => {
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
        const x = d3.scaleBand()
              .range([ 0, width ])
              .domain(values.map(function(d) { return d[0]; }))
              .padding(0.2);

        svg.append("g")
            .attr("transform", "translate(0," + height + ")")
            .call(d3.axisBottom(x))
            .selectAll("text")
            .style("text-anchor", "end")
            .attr("transform", "rotate(-25)")
        ;

        // Add Y axis
        var y = d3.scaleLinear()
            .domain([0, Math.max(...values.map(v => v[1]))])
            .range([ height, 0]);
        svg.append("g")
            .call(d3.axisLeft(y));

        // Add dots
        svg.selectAll('mybar')
            .data(values)
            .enter()
            .append("rect")
            .attr('x', function(d) {return x(d[0]);})
            .attr('y', function(d) {return y(d[1]);})
            .attr("width", x.bandwidth())
            .attr("height", function(d) { return height - y(d[1]); })
            .attr("fill", "#69b3a2");
    });
};

const run = async () => {
    console.log("loading db...")
    console.time("DB load")
    const db = await load_db();
    console.log("DB:", db);
    console.timeEnd("DB load")

    const testbar = document.getElementById('testbar');

    // set the dimensions and margins of the graph
    var margin = {top: 10, right: 30, bottom: 80, left: 80},
        width = document.body.clientWidth - margin.left - margin.right,
        height = document.body.clientHeight - margin.top - margin.bottom - testbar.clientHeight;

    // append the svg object to the body of the page
    const svg = d3.select("#viz_area")
    //  .attr("width", width + margin.left + margin.right)
    //  .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform",
              "translate(" + margin.left + "," + margin.top + ")");

    const input = testbar.getElementsByTagName('input')[0];
    const barplot_btn = testbar.querySelector('button[name="barplot"]');

    barplot_btn.onclick = () => render_query_barplot(
        db,
        input.value,
        {},
        {svg, margin},
    );
    barplot_btn.onclick();
};
window.onload = run;
