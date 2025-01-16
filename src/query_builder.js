const wire_svg = (dom) => {
    const on_field_click_listeners = [];

    const wire_node = (node) => {
        const texts = Array.from(node.getElementsByTagName('text'));
        const [titleEl, _] = texts.splice(0, 2);
        titleEl.classList.add('nodetitle');
        
        const fields = [];
        for (const fieldEl of texts) {
            fields.push(fieldEl);
            fieldEl.classList.add('nodefield');

            fieldEl.onclick = () => {
                console.log(fieldEl, fieldEl.textContent, "of", titleEl.textContent)
                for (const listener of on_field_click_listeners) {
                    listener(node, fieldEl, titleEl)
                }
            }
        }

        return {
            node,
            titleEl,
            title: titleEl.textContent,
            fields,
        }
    };

    const nodes = [];
    for (const node of dom.getElementsByClassName('node')) {
        nodes.push(wire_node(node));
    }

    const listen_on_node_click = (listener) => on_field_click_listeners.push(listener);

    const find_node = (node_name) => {
        for (const node of nodes) {
            if (node.title.toUpperCase() == node_name.toUpperCase()) {
                return node;
            }
        }
    };

    const scroll_to_node = (node_name) => {
        const node = find_node(node_name);
        const bbox = node.node.getBoundingClientRect();

        dom.style.top = -bbox.top + 20 + 'px';

        const xcenter = bbox.left + bbox.width / 2;
        dom.style.left = -xcenter + document.body.clientWidth / 2 + 'px';
    }

    return {
        nodes,
        dom,
        find_node,
        scroll_to_node,
        listen_on_node_click,
    };
};

const show_query_builder = (builder_space, graph_svg) => {
    builder_space.setAttribute('disabled', 'false');
    builder_space.innerHTML = graph_svg;

    const svg = builder_space.firstElementChild;

    builder_space.style.top = 0;
    builder_space.style.left = 0;
    builder_space.style.width = parseInt(svg.getAttribute('width')) + 'px';
    builder_space.style.height = parseInt(svg.getAttribute('height')) + 'px';
    svg.style.width = parseInt(svg.getAttribute('width')) + 'px';
    svg.style.height = parseInt(svg.getAttribute('height')) + 'px';

    const queryBuilder = wire_svg(builder_space);
    window.queryBuilder = queryBuilder;  // We expose this globally for easier tests

    queryBuilder.scroll_to_node('CVE');

    const selectedFields = [];

    queryBuilder.listen_on_node_click((node, fieldEl, titleEl) => {
        let now_selected = true;
        for (const selected_field of selectedFields) {
            if (selected_field === fieldEl)  {
                now_selected = false;
                break;
            }
        }

        if (now_selected) {
            fieldEl.classList.add('selected');
            selectedFields.push(fieldEl);
        }
        else {
            fieldEl.classList.remove('selected');
            const pos = selectedFields.indexOf(fieldEl);
            selectedFields.splice(pos, 1);
        }

        console.log('Selected', selectedFields);

        if (selectedFields.length > 0 && selectedFields.length < 4) {
            // TODO: ENABLE FAB
        }
    });

    return queryBuilder;
}
