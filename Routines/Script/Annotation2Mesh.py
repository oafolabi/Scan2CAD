import sys
assert sys.version_info >= (3, 5)

import numpy as np
import pathlib
import os
import shutil
import glob
import JSONHelper
import CSVHelper
import csv
import quaternion
from plyfile import (PlyData, PlyElement, make2d, PlyParseError, PlyProperty)
import pywavefront
import argparse

# params
parser = argparse.ArgumentParser()                                                                                                                                                                                                                                                                                        
parser.add_argument('--out', default="./meshes/", help="outdir")
opt = parser.parse_args()

def get_catid2index(filename):
    catid2index = {}
    csvfile = open(filename) 
    spamreader = csv.DictReader(csvfile, delimiter='\t')
    for row in spamreader:
        try:
            catid2index[row["wnsynsetid"][1:]] = int(row["nyu40id"])
        except:
            pass
    csvfile.close()

    return catid2index

def make_M_from_tqs(t, q, s):
    q = np.quaternion(q[0], q[1], q[2], q[3])
    T = np.eye(4)
    T[0:3, 3] = t
    R = np.eye(4)
    R[0:3, 0:3] = quaternion.as_rotation_matrix(q)
    S = np.eye(4)
    S[0:3, 0:3] = np.diag(s)

    M = T.dot(R).dot(S)
    return M 

def decompose_mat4(M):
    R = M[0:3, 0:3]
    sx = np.linalg.norm(R[0:3, 0])
    sy = np.linalg.norm(R[0:3, 1])
    sz = np.linalg.norm(R[0:3, 2])

    s = np.array([sx, sy, sz])

    R[:, 0] /= sx;
    R[:, 1] /= sy;
    R[:, 2] /= sz;
    q = quaternion.from_rotation_matrix(R[0:3, 0:3])

    t = M[0:3, 3]
    return t, q, s

if __name__ == '__main__':
    params = JSONHelper.read("./Parameters.json") # <-- read parameter file (contains dataset paths)

    faces0 = []
    verts0 = []
    norms0 = []
    scan_file = ""
    for r in JSONHelper.read(params["annotations"] + "/full_annotations.json"):
        id_scan = r["id_scan"]
        if id_scan != "scene0567_01":
            continue
        for model in r["aligned_models"]:
            t = model["trs"]["translation"]
            q = model["trs"]["rotation"]
            s = model["trs"]["scale"]

            id_cad = model["id_cad"]
            catid_cad = model["catid_cad"]

            outdir = os.path.abspath(opt.out + "/" + id_scan)
            pathlib.Path(outdir).mkdir(parents=True, exist_ok=True) 


            if scan_file == "": # <-- do just once, because scene is same for all cad models
                scan_file = params["scannet"] + "/" + id_scan + "/" + id_scan + "_vh_clean_2.ply"
                Mscan = make_M_from_tqs(r["trs"]["translation"], r["trs"]["rotation"], r["trs"]["scale"])
                assert os.path.exists(scan_file), scan_file + " does not exist."
                with open(scan_file, 'rb') as read_file:
                    mesh_scan = PlyData.read(read_file)
                for v in mesh_scan["vertex"]: 
                    v1 = np.array([v[0], v[1], v[2], 1])
                    v1 = np.dot(Mscan, v1)

                    v[0] = v1[0]
                    v[1] = v1[1]
                    v[2] = v1[2]

                with open(outdir + "/scan.ply", mode='wb') as f:
                    PlyData(mesh_scan).write(f)

            cad_file = params["shapenet"] + "/" + catid_cad + "/" + id_cad  + "/models/model_normalized.obj"
            cad_mesh = pywavefront.Wavefront(cad_file, collect_faces=True, parse=True)
            Mcad = make_M_from_tqs(t, q, s)

            print("CAD", cad_file, "n-verts", len(cad_mesh.vertices))
            color = (50, 200, 50)
            faces = []
            verts = []
            norms = []
            for name, mesh in cad_mesh.meshes.items():
                for f in mesh.faces:
                    faces.append((np.array(f[0:3]) + len(verts0),))
                    v0 = cad_mesh.vertices[f[0]]
                    v1 = cad_mesh.vertices[f[1]]
                    v2 = cad_mesh.vertices[f[2]]
                    if len(v0) == 3:
                        cad_mesh.vertices[f[0]] = v0 + color
                    if len(v1) == 3:
                        cad_mesh.vertices[f[1]] = v1 + color
                    if len(v2) == 3:
                        cad_mesh.vertices[f[2]] = v2 + color
            faces0.extend(faces)
            
            for v in cad_mesh.vertices[:]:
                if len(v) != 6:
                    v = (0, 0, 0) + (0, 0, 0)
                vi = tuple(np.dot(Mcad, np.array([v[0], v[1], v[2], 1]))[0:3])
                ci = tuple(v[3:6])
                verts.append(vi + ci)
            verts0.extend(verts)

    verts0 = np.asarray(verts0, dtype=[('x', 'f4'), ('y', 'f4'), ('z', 'f4'), ('red', 'u1'), ('green', 'u1'), ('blue', 'u1')])
    faces0 = np.asarray(faces0, dtype=[('vertex_indices', 'i4', (3,))])
    objdata = PlyData([PlyElement.describe(verts0, 'vertex', comments=['vertices']),  PlyElement.describe(faces0, 'face')], comments=['faces'])
    savename = outdir + "/alignment.ply"
    print("alignment saved",savename)
    with open(savename, mode='wb') as f:
        PlyData(objdata).write(f)


