import sys
import json
import numpy as np
import random
import overpass
import geojson
import matplotlib.pyplot as plt
from math import sqrt, exp, log
from scipy.spatial import KDTree

def read_file(file_path):
    content = ""
    with open(file_path, 'r') as f:
        for line in f:
            content += line
    return content

def get_osm_ways_in_bbox(lat1, lon1, lat2, lon2):
    query = 'way[highway][!area]["highway"~"primary|secondary|tertiary|residential|unclassified"]' + \
        '(' + str(lat1) + ', ' + str(lon1) + ', ' + str(lat2) + ', ' + lon2 + ')'
    api = overpass.API()
    return api.Get(query)

def normal(x, mu, sigma):
    return exp(-(x - mu) ** 2 / (2 * sigma ** 2)) / sqrt(2 * (sigma ** 2) * np.pi)

def sidewalk_dist(way, children):
    sigma_d = 0.00002
    sigma_x = 0.00002
    mean = 0.00006
    best_d = None
    max_l = float("-inf")

    ls = []
    # print len(children)
    d_range = np.arange(mean - sigma_d * 3, mean + sigma_d * 3, 0.000001)
    for d in d_range:
        log_likelihood = log(normal(d, mean, sigma_d))
        for x in children:
            log_likelihood += log(normal(x, d, sigma_x))
        ls += [log_likelihood]
        if log_likelihood > max_l:
            best_d = d
            max_l = log_likelihood
    # print best_d
    # plt.plot(d_range, ls)
    # plt.show()

    return best_d

def add_sidewalk(output, way, sidewalk_nodes):    
    for i in range(2):
        nodes = []
        for node in sidewalk_nodes:        
            next_node_id = int(random.random() * 100000000000)
            nodes += [next_node_id]
            output["elements"] += [{
                "type": "node",
                "id": next_node_id,
                "lat": node[i][0],
                "lon": node[i][1]
            }]
        next_way_id = int(random.random() * 100000000000)
        output["elements"] += [{
                "type": "way",
                "id": next_way_id,
                "nodes": nodes,
                "tags": { "highway": "sidewalk" }
            }]

# only data points within max_dis of the ways are considered
def get_children_data_points(ways, nodes, max_dis = 0.00012):
    children = [[] for i in range(len(ways))]
    children_points = [[] for i in range(len(ways))]
    print "analyzing data points and segments"

    for i in range(len(ways)):
        sys.stdout.write('\r' + str(i) + "/" + str(len(ways)))
        way = ways[i]
        num_nodes = len(way["nodes"])
        
        for j in range(1, num_nodes):
            n1 = nodes[way["nodes"][j - 1]]
            n2 = nodes[way["nodes"][j]]
            mid = np.array([(n1 + n2) / 2.])

            # consider the top k points that are at most distance_upper_bound from the midpoint
            _, neighbor_indexes = data_kd_tree.query(mid, k=1000, distance_upper_bound=0.01)
            neighbor_indexes = np.array([idx for idx in neighbor_indexes[0] \
                if idx >= 0 and idx < data_kd_tree.data.shape[0]])

            if neighbor_indexes.shape[0] > 0:
                neighbors = data_kd_tree.data[neighbor_indexes]
                for x in neighbors:
                    # point of perpendicular in between two points
                    # print (n1 - n2).dot(x - n2) * (n2 - n1).dot(x - n1)
                    if (n1 - n2).dot(x - n2) >= 0 and (n2 - n1).dot(x - n1) >= 0:
                        direction = (n2 - n1) / np.linalg.norm(n2 - n1)
                        # print abs(direction.dot(x - n1))
                        if abs(direction.dot(x - n1)) < max_dis:
                            children[i] += [abs(direction.dot(x - n1))]
                            children_points[i] += [x]
    print "\t done"
    for i in range(len(ways)):
        lngs = [point[1] for point in children_points[i]]
        lats = [point[0] for point in children_points[i]]
        plt.plot(lngs, lats, 'o', alpha=0.1, linewidth='0')
        # plt.show()
    plt.axis("equal")
    plt.show()

    return children

def generate_sidewalks(osm_json):
    sidewalk_json = {
        "version": 0.6,
        "generator": "Overpass API",
        "osm3s": {
            "timestamp_osm_base": "2016-11-29T06:59:03Z",
            "copyright": "The data included in this document is from www.openstreetmap.org. The data is made available under ODbL."
        },
        "elements": []
    }
    
    nodes = {}  # maps from node id to (lat, lon) np vector
    ways = []   # list of way elements

    for element in osm_json["elements"]:
        if element["type"] == "node":
            nodes[element["id"]] = np.array([element["lat"], element["lon"]])
        elif element["type"] == "way":
            ways += [element]

    print "number of ways: " + str(len(ways))

    children_data_points = get_children_data_points(ways, nodes)
    
    for i in range(len(children_data_points)):
        plt.plot(children_data_points[i], [i] * len(children_data_points[i]), 'x')
    plt.show()

    
    print "predicting sidewalk locations"
    d_hats = []
    for t in range(len(ways)):
        sys.stdout.write('\r' + str(t) + "/" + str(len(ways)))

        way = ways[t]
        num_nodes = len(way["nodes"])
        if num_nodes > 1:
            n1 = nodes[way["nodes"][0]]
            n2 = nodes[way["nodes"][1]]
            # unit vector of center line direction
            direction = (n2 - n1) / np.linalg.norm(n2 - n1)
            orth_direction = np.array([-direction[1], direction[0]])

            # expected distance from centerline
            d = sidewalk_dist(way, children_data_points[t])
            d_hats += [d]
            # print d

            # list of sidewalk waypoint pairs (left, right)
            sidewalk_nodes = [tuple([n1 - orth_direction * d, n1 + orth_direction * d])]
            prev_direction = direction

            # print num_nodes
            for i in range(2, num_nodes):
                n1 = nodes[way["nodes"][i - 1]]
                n2 = nodes[way["nodes"][i]]
                direction = (n2 - n1) / np.linalg.norm(n2 - n1)
                orth_direction = np.array([-direction[1], direction[0]])
                sidewalk_nodes += [tuple([n1 - orth_direction * d, n1 + orth_direction * d])]    
                prev_direction = direction

            # last node
            sidewalk_nodes += [tuple([n2 - orth_direction * d, n2 + orth_direction * d])]

            add_sidewalk(sidewalk_json, way, sidewalk_nodes)
    
    weights_d_hats = np.ones_like(d_hats) / len(d_hats)
    plt.hist(d_hats, 50, weights=weights_d_hats, facecolor='green', alpha=0.75)

    plt.show()
    print "\t done"

    # print sidewalk_nodes
    pretty_json = json.dumps(sidewalk_json, indent=2, separators=(',', ': '))

    print "wrote to output.json in osm json format"
    output_file = open('output.json', 'w')
    output_file.write(pretty_json)

    return sidewalk_json

def load_strava_points_from_file(strava_points_file):
    return np.array(json.loads(read_file(strava_points_file)))

def generate_sidewalks_from_file(osm_json_file):
    osm_content = read_file(osm_json_file)
    osm_json = json.loads(osm_content)
    return generate_sidewalks(osm_json)



data_points = load_strava_points_from_file("all_points.json")
data_kd_tree = KDTree(data_points)
print "number of total data points: " + str(len(data_points))

if __name__ == "__main__":
    if len(sys.argv) == 2:
        osm_file_name = sys.argv[1]
        generate_sidewalks_from_file(osm_file_name)
    else:
        print "Usage: python generate_sidewalks.py <osm_json_file>"
