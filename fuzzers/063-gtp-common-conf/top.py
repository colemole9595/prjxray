#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2017-2020  The Project X-Ray Authors.
#
# Use of this source code is governed by a ISC-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/ISC
#
# SPDX-License-Identifier: ISC

import json
import os
import random
from collections import namedtuple

random.seed(int(os.getenv("SEED"), 16))
from prjxray import util
from prjxray import verilog
from prjxray.db import Database

INT = "INT"
BIN = "BIN"


def gen_sites(site):
    db = Database(util.get_db_root(), util.get_part())
    grid = db.grid()
    for tile_name in sorted(grid.tiles()):
        loc = grid.loc_of_tilename(tile_name)
        gridinfo = grid.gridinfo_at_loc(loc)

        if gridinfo.tile_type not in [
                "GTP_COMMON",
                "GTP_COMMON_MID_RIGHT",
        ]:
            continue
        else:
            tile_type = gridinfo.tile_type

        for site_name, site_type in gridinfo.sites.items():
            if site_type != site:
                continue

            yield tile_name, tile_type, site_name, site_type


def main():
    print(
        '''
module top(
    input wire in,
    output wire out
);

assign out = in;
''')

    params_dict = {"tile_type": None}
    params_list = list()

    for tile_name, tile_type, site_name, site_type in gen_sites(
            "GTPE2_COMMON"):

        if params_dict["tile_type"]:
            assert tile_type == params_dict["tile_type"]
        else:
            params_dict["tile_type"] = tile_type

        params = dict()
        params['site'] = site_name

        verilog_attr = ""

        verilog_attr = "#("

        fuz_dir = os.getenv("FUZDIR", None)
        assert fuz_dir
        with open(os.path.join(fuz_dir, "attrs.json"), "r") as attrs_file:
            attrs = json.load(attrs_file)

        in_use = bool(random.randint(0, 9))
        params["IN_USE"] = in_use

        if in_use:
            for param, param_info in attrs.items():
                param_type = param_info["type"]
                param_values = param_info["values"]
                param_digits = param_info["digits"]

                if param_type == INT:
                    value = random.choice(param_values)
                    value_str = value
                else:
                    assert param_type == BIN
                    value = random.randint(0, param_values[0])
                    value_str = "{digits}'b{value:0{digits}b}".format(
                        value=value, digits=param_digits)

                params[param] = value

                verilog_attr += """
            .{}({}),""".format(param, value_str)

            for param in ["GTGREFCLK1", "GTGREFCLK0", "PLL0LOCKDETCLK",
                          "PLL1LOCKDETCLK", "DRPCLK"]:
                is_inverted = random.randint(0, 1)

                params[param] = is_inverted

                verilog_attr += """
            .IS_{}_INVERTED({}),""".format(param, is_inverted)

            verilog_attr = verilog_attr.rstrip(",")
            verilog_attr += "\n)"

            print("(* KEEP, DONT_TOUCH, LOC=\"{}\" *)".format(site_name))
            print(
                """GTPE2_COMMON {attrs} {site} (
        .GTREFCLK0(1'b0),
        .GTREFCLK1(1'b0)
    );""".format(attrs=verilog_attr, site=site_name))

        params_list.append(params)

    clkswing_cfg_tiles = dict()
    for tile_name, _, site_name, site_type in gen_sites("IBUFDS_GTE2"):
        # Both the IBUFDS_GTE2 in the same tile need to have
        # the same CLKSWING_CFG parameter
        if tile_name not in clkswing_cfg_tiles:
            clkswing_cfg = random.randint(0, 3)
            clkswing_cfg_tiles[tile_name] = clkswing_cfg
        else:
            clkswing_cfg = clkswing_cfg_tiles[tile_name]

        in_use = bool(random.randint(0, 9))
        params = {
            "site":
            site_name,
            "tile":
            tile_name,
            "IN_USE":
            in_use,
            "CLKRCV_TRST":
            verilog.quote("TRUE" if random.randint(0, 1) else "FALSE"),
            "CLKCM_CFG":
            verilog.quote("TRUE" if random.randint(0, 1) else "FALSE"),
            "CLKSWING_CFG":
            clkswing_cfg,
        }

        if in_use:
            print("(* KEEP, DONT_TOUCH, LOC=\"{}\" *)".format(site_name))
            print(
                """
IBUFDS_GTE2 #(
    .CLKRCV_TRST({CLKRCV_TRST}),
    .CLKCM_CFG({CLKCM_CFG}),
    .CLKSWING_CFG({CLKSWING_CFG})
) {site} (
    );""".format(**params))

        params_list.append(params)

    print("endmodule")

    params_dict["params"] = params_list
    with open('params.json', 'w') as f:
        json.dump(params_dict, f, indent=2)


if __name__ == '__main__':
    main()