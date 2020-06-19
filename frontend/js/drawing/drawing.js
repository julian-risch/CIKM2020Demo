import { emitter, E } from '../env/events.js'
import { data } from '../env/data.js';
import { ELEMENTS } from '../env/elements.js';
import { Layout } from './layout.js';
import { Lasso } from "./lasso.js";
import { DRAWING_CONFIG as CONFIG } from "./config.js";

class Comments {
    constructor() {
        this.splits = [];
        this.lookup = {};

        let counter = 0;
        Object.keys(data.comments).forEach((commentId) => {
            this.lookup[commentId] = [];
            data.comments[commentId].splits.forEach((split, j) => {
                this.splits.push({
                    orig_id: [commentId, j],
                    text: data.getCommentText(commentId, j),

                });
                this.lookup[commentId].push(counter);
                counter++;
            });
        });
        this.edges = data.edges.map(edge => {
            try {
                return {
                    source: this.lookup[data.idx2id[edge.src[0]]][edge.src[1]],
                    target: this.lookup[data.idx2id[edge.tgt[0]]][edge.tgt[1]],
                    weights: edge.wgts,
                    src: edge.src,
                    tgt: edge.tgt
                }
            } catch (e) {
                console.log(edge);
                console.log(this.lookup);
                console.log(edge.src[0], data.idx2id[edge.src[0]], this.lookup[data.idx2id[edge.src[0]]]);
                throw e;
            }
        });

        this.highlightActive = false;

        this.eventlisteners = [
            emitter.on(E.DRAWING_CONFIG_CHANGED, this.onConfigChange.bind(this)),
            emitter.on(E.COMMENT_SELECTED, this.highlightComment.bind(this)),
            emitter.on(E.FILTERS_UPDATED, this.onFilterUpdate.bind(this))];
    }

    draw(parent) {
        this.ROOT = parent.append('g');

        this.LINKS = parent.append('g')
            .attr('stroke', CONFIG.STYLES.DEFAULT.EDGE_STROKE)
            .attr('stroke-opacity', CONFIG.LINKS_VISIBLE ? CONFIG.STYLES.DEFAULT.EDGE_OPACITY : 0)
            .selectAll('line')
            .data(this.edges)
            .join('line')
            .attr('stroke-width', d => Math.sqrt(d.value / 50));

        this.NODES = this.ROOT
            .selectAll('circle')
            .data(this.splits)
            .enter()
            .append('circle')
            .attr('stroke', CONFIG.STYLES.DEFAULT.NODE_STROKE)
            .attr('stroke-width', CONFIG.STYLES.DEFAULT.NODE_STROKE_WIDTH)
            // TODO make this weight dependent
            .attr('r', d => 1.0 * CONFIG.STYLES.DEFAULT.BASE_RADIUS)
            .attr('fill', CONFIG.STYLES.DEFAULT.NODE_FILL)
            .on('click', this.nodeOnClick.bind(this));
    }

    onFilterUpdate() {
        // defaults:
        let radius = d => 1.0 * CONFIG.STYLES.DEFAULT.BASE_RADIUS;
        let opacity = CONFIG.STYLES.DEFAULT.NODE_OPACITY;
        let fill = CONFIG.STYLES.DEFAULT.NODE_FILL;

        if (data.activeFilters.highlight) {
            opacity = (d) => CONFIG.style('NODE_OPACITY', 'HIGHLIGHT',
                data.comments[d.orig_id[0]].activeFilters.highlight);
            fill = (d) => CONFIG.style('NODE_FILL', 'HIGHLIGHT',
                data.comments[d.orig_id[0]].activeFilters.highlight);
        }

        if (data.activeFilters.timeRange) {
            // TODO make this weight dependent
            radius = (d) => 1 * CONFIG.style('BASE_RADIUS', 'TIME_RANGE',
                data.comments[d.orig_id[0]].activeFilters.timeRange);
            opacity = (d) => CONFIG.style('NODE_OPACITY', 'TIME_RANGE',
                data.comments[d.orig_id[0]].activeFilters.timeRange);
        }

        this.NODES.attr('r', radius);
        this.NODES.attr('opacity', opacity);
        this.NODES.attr('fill', fill);
    }

    highlightComment(commentId) {
        if (data.activeFilters.highlight !== false) {
            data.comments[data.activeFilters.highlight].activeFilters.highlight = false;
            data.activeFilters.highlight = false;
        } else {
            data.comments[commentId].activeFilters.highlight = true;
            data.activeFilters.highlight = commentId;
        }

        emitter.emit(E.FILTERS_UPDATED, data.comments);
    }

    nodeOnClick(e) {
        emitter.emit(E.COMMENT_SELECTED, e.orig_id[0]);
    }

    onTick() {
        if (CONFIG.LINKS_VISIBLE) {
            this.LINKS
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);
        }
        this.NODES
            .attr('transform', d => 'translate(' + d.x + ',' + d.y + ')');
    }

    onConfigChange(key, value) {
        if (key === 'LINKS_VISIBLE') {
            this.LINKS.attr('stroke-opacity', value ? CONFIG.STYLES.DEFAULT.EDGE_OPACITY : 0);
            if (value) this.onTick();
        }
    }

    attachSimulation(simulation) {
        simulation.on('tick', this.onTick.bind(this));
        this.NODES.call(Layout.drag(simulation));
    }

    destructor() {
        this.eventlisteners.forEach((listener) => emitter.off(listener));
        this.NODES.remove();
        this.LINKS.remove();
        delete this.splits;
        delete this.lookup;
        delete this.edges;
    }
}

class ComExDrawing {
    constructor(parent) {
        this.ROOT = d3.select(parent).append('svg');
        this.MAIN_GROUP = this.ROOT.append('g');

        this.MOUSE_SETTINGS_ZOOM = document.getElementById('mouse-settings-zoom');
        this.MOUSE_SETTINGS_ZOOM.addEventListener('change', this.updateMouseMode.bind(this));
        this.MOUSE_SETTINGS_SELECT = document.getElementById('mouse-settings-select');
        this.MOUSE_SETTINGS_SELECT.addEventListener('change', this.updateMouseMode.bind(this));
        this.MOUSE_SETTINGS_CENTRE = document.getElementById('mouse-settings-centre');
        this.MOUSE_SETTINGS_CENTRE.addEventListener('click', this.centreZoom.bind(this));

        this.createScales();

        emitter.on(E.REDRAW, this.draw.bind(this));
    }

    draw() {
        this.deconstruct();

        this.setDimensions();
        this.initZoom();
        this.updateMouseMode();

        this.COMMENTS = new Comments();
        console.log(this.COMMENTS);

        this.COMMENTS.draw(this.MAIN_GROUP);
        this.LAYOUT = new Layout(this.COMMENTS.splits, this.COMMENTS.edges);
        this.LASSO = new Lasso(this.ROOT, this.COMMENTS.NODES);
        this.COMMENTS.attachSimulation(this.LAYOUT.simulation);
        this.ROOT.node();
    }

    updateMouseMode() {
        let modes = this.getMouseMode();
        if (modes.zoom) {
            this.ZOOM.filter(() => modes.zoom);
        } else {
            this.ZOOM.filter(null);
            this.LASSO.attachLasso();
        }

        //if (modes.lasso)
    }

    getMouseMode() {
        return {
            zoom: this.MOUSE_SETTINGS_ZOOM.checked,
            lasso: this.MOUSE_SETTINGS_SELECT.checked
        }
    }

    createScales() {
        this.xScale = d3.scaleLinear()
            .range([0, this.canvasWidth])
            .domain([0, CONFIG.WIDTH]);
        this.yScale = d3.scaleLinear()
            .range([0, this.canvasHeight])
            .domain([0, CONFIG.HEIGHT]);
    }

    centreZoom() {
        this.ZOOM.scaleTo(this.MAIN_GROUP, 1);
        // FIXME: somehow is 0 0 not the centroid
        this.ZOOM.translate([0, 0])//this.MAIN_GROUP, -0.5,0.5);
    }

    initZoom() {
        if (!this.ZOOM) {
            this.ZOOM = d3.zoom()
                .scaleExtent([0.1, 8])
                .on('zoom', () => {
                    this.MAIN_GROUP.attr('transform', d3.event.transform);
                });
            this.ROOT.call(this.ZOOM);
        }
        this.ZOOM.extent([[0, 0], [CONFIG.WIDTH, CONFIG.HEIGHT]]);
    }

    setDimensions() {
        let parent = this.ROOT.node().parentElement;
        this.canvasWidth = parent.clientWidth;
        this.canvasHeight = parent.clientHeight;
        CONFIG.HEIGHT = this.canvasHeight;
        CONFIG.WIDTH = this.canvasWidth;

        this.ROOT
            .attr('viewBox', [0, 0, this.canvasWidth, this.canvasHeight])
            .attr('height', this.canvasHeight);
    }

    deconstruct() {
        if (this.COMMENTS) {
            this.COMMENTS.destructor();
            delete this.COMMENTS;
        }
        if (this.LAYOUT) {
            this.LAYOUT.deconstructor();
            delete this.LAYOUT;
        }
    }
}

export { ComExDrawing };