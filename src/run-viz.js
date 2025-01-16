const load_db = async () => {
    const worker = new Worker('./sqljs/v1.12.0/worker.sql-wasm.js')
    const sqlPromise = initSqlJs({
        locateFile: file => `./sqljs/v1.12.0/${file}`
    });
    const dataPromise = fetch(
        "../data/merged.sqlite",
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
            if (Object.keys(params || {}).length == 0) {
                console.debug("Running query", query);
            }
            else {
                console.debug("Running query", query, "params", params);
            }
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

    // Open the file
    worker.postMessage({
        id: next_id++,
        action:"open",
        buffer: buf,
    });

    return dbConnection;
}

const run = async () => {
    for (const btn of document.getElementsByTagName('button')) {
        btn.disabled = true;
    }
    console.log("loading db...")
    console.time("DB load")
    const db = await load_db();
    console.log("DB:", db);
    console.timeEnd("DB load")

    for (const btn of document.getElementsByTagName('button')) {
        btn.disabled = false;
    }

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
    const percent_barplot_btn = testbar.querySelector('button[name="percent_barplot"]');
    const lineplot_btn = testbar.querySelector('button[name="lineplot"]');
    const areaplot_btn = testbar.querySelector('button[name="areaplot"]');

    barplot_btn.onclick = () => render_query_barplot(
        db,
        input.value,
        {},
        {svg, margin},
    );
    percent_barplot_btn.onclick = () => render_query_barplot(
        db,
        input.value,
        {},
        {svg, margin},
        {percent_stack_plot: true}
    );
    lineplot_btn.onclick = () => render_query_lineplot(
        db,
        input.value,
        {},
        {svg, margin},
    );
    areaplot_btn.onclick = () => render_query_areaplot(
        db,
        input.value,
        {},
        {svg, margin},
    );

};
window.onload = run;
