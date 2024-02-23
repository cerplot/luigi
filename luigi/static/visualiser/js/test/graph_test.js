module("graph.js");

test("nodeFromStep", function() {
    var step = {
        deps: ["B","C"],
        stepId: "A",
        status: "DONE"
    };
    var expected = {
        stepId: "A",
        status: "DONE",
        trackingUrl: "#A",
        deps: ["B","C"],
        depth: -1
    };
    deepEqual(Graph.testableMethods.nodeFromStep(step), expected);
});

test("uniqueIndexByProperty", function() {
    var input = [
        {a:"x", b:100},
        {a:"y", b:101},
        {a:"z", b:102}
    ];
    var expected = {
        "x": 0,
        "y": 1,
        "z": 2
    };
    deepEqual(Graph.testableMethods.uniqueIndexByProperty(input, "a"), expected);
});

test("createDependencyEdges", function() {
    var A = {stepId: "A", deps: ["B","C"]};
    var B = {stepId: "B", deps: ["D"]};
    var C = {stepId: "C", deps: []};
    var D = {stepId: "D", deps: []};
    var nodes = [A,B,C,D];
    var nodeIndex = {"A":0, "B":1, "C":2, "D":3};
    var edges = Graph.testableMethods.createDependencyEdges(nodes, nodeIndex);
    var expected = [
        {source: A, target: B},
        {source: A, target: C},
        {source: B, target: D}
    ];
    deepEqual(edges, expected);
});

test("computeDepth", function() {
    var A = {stepId: "A", deps: ["B","C"], depth:-1};
    var B = {stepId: "B", deps: ["D"], depth:-1};
    var C = {stepId: "C", deps: [], depth:-1};
    var D = {stepId: "D", deps: [], depth:-1};
    var E = {stepId: "C", deps: [], depth:-1};
    var nodes = [A,B,C,D,E];
    var nodeIndex = {"A":0, "B":1, "C":2, "D":3};
    Graph.testableMethods.computeDepth(nodes, nodeIndex);
    equal(A.depth, 0);
    equal(B.depth, 1);
    equal(C.depth, 1);
    equal(D.depth, 2);
    equal(E.depth, -1);
});

test("computeRowsSelfDeps", function () {
    var A1 = {name: "A", stepId: "A1", deps: ["A2"], depth: -1}
    var A2 = {name: "A", stepId: "A2", deps: [], depth: -1}
    var nodes = [A1, A2]
    var nodeIndex = {"A1": 0, "A2": 1}
    var rowSizes = Graph.testableMethods.computeRows(nodes, nodeIndex)
    equal(A1.depth, 0)
    equal(A2.depth, 1)
    equal(rowSizes, [1, 1])
});

test("computeRowsGrouped", function() {
    var A0 = {name: "A", stepId: "A0", deps: ["D0", "B0"], depth: -1}
    var B0 = {name: "B", stepId: "B0", deps: ["C1", "C2"], depth: -1}
    var C1 = {name: "C", stepId: "C1", deps: ["D1", "E1"], depth: -1}
    var C2 = {name: "C", stepId: "C2", deps: ["D2", "E2"], depth: -1}
    var D0 = {name: "D", stepId: "D0", deps: [], depth: -1}
    var D1 = {name: "D", stepId: "D1", deps: [], depth: -1}
    var D2 = {name: "D", stepId: "D2", deps: [], depth: -1}
    var E1 = {name: "E", stepId: "E1", deps: [], depth: -1}
    var E2 = {name: "E", stepId: "E2", deps: [], depth: -1}
    var rowSizes = Graph.testableMethods.computeRows(nodes, nodeIndex)
    equal(A0.depth, 0)
    equal(B0.depth, 1)
    equal(C1.depth, 2)
    equal(C2.depth, 2)
    equal(D0.depth, 3)
    equal(D1.depth, 3)
    equal(D2.depth, 3)
    equal(E1.depth, 4)
    equal(E2.depth, 4)
    equal(rowSizes, [1, 1, 2, 3, 2])
});

test("createGraph", function() {
    var steps = [
        {stepId: "A", deps: ["B","C"], status: "PENDING"},
        {stepId: "B", deps: ["D"], status: "RUNNING"},
        {stepId: "C", deps: [], status: "DONE"},
        {stepId: "D", deps: [], status: "DONE"},
        {stepId: "E", deps: [], status: "DONE"}
    ];
    var graph = Graph.testableMethods.createGraph(steps);
    equal(graph.nodes.length, 4);
    equal(graph.links.length, 3);
    $.each(graph.nodes, function() {
        notEqual(this.x, 0);
        notEqual(this.y, 0);
    });

    // TODO: more assertions
});
