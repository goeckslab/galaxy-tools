#!/usr/bin/env python
from __future__ import print_function

import argparse
import json
import logging
import shutil
import sys
import time

from webapollo import AssertUser, GuessOrg, OrgOrGuess, WAAuth, WebApolloInstance
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def checkPermission(permission):
    if permission in group["permissions"]:
        return True
    return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create or update an organism in an Apollo instance')
    WAAuth(parser)

    parser.add_argument('jbrowse', help='JBrowse Data Directory')
    parser.add_argument('email', help='User Email')
    OrgOrGuess(parser)
    parser.add_argument('--genus', help='Organism Genus')
    parser.add_argument('--species', help='Organism Species')
    parser.add_argument('--public', action='store_true', help='Make organism public')
    parser.add_argument('--group', help='Give access to a user group')
    parser.add_argument('--remove_old_directory', action='store_true', help='Remove old directory')

    args = parser.parse_args()
    wa = WebApolloInstance(args.apollo, args.username, args.password)

    org_cn = GuessOrg(args, wa)
    if isinstance(org_cn, list):
        org_cn = org_cn[0]

    # User must have an account
    gx_user = AssertUser(wa.users.loadUsers(email=args.email))

    log.info("\tDetermining if add or update required")
    try:
        org = wa.organisms.findOrganismByCn(org_cn)
    except Exception:
        org = None

    if org:
        has_perms = False
        old_directory = org['directory']
        # update the organism if the gx_user is global admin or organism administrative
        for user_owned_organism in gx_user.organismPermissions:
            if user_owned_organism['organism'] == org['commonName'] and 'ADMINISTRATE' in user_owned_organism['permissions']:
                has_perms = True
                break
        if not has_perms and gx_user.role != 'ADMIN':
            sys.exit("Naming Conflict. You do not have permissions to access this organism. Either request permission from the owner, or choose a different name for your organism.")

        log.info("\tUpdating Organism %s", org_cn)
        data = wa.organisms.updateOrganismInfo(
            org['id'],
            org_cn,
            args.jbrowse,
            # mandatory
            genus=args.genus,
            species=args.species,
            public=args.public
        )
        time.sleep(2)
        if args.remove_old_directory and args.jbrowse != old_directory:
            shutil.rmtree(old_directory)

        data = [wa.organisms.findOrganismById(org['id'])]

    else:
        # New organism
        # create an organism if the gx_user is global admin or instructor
        if gx_user.role != 'INSTRUCTOR' and gx_user.role != 'ADMIN':
            sys.exit(gx_user.role + " is not authorized to create an organisms")
        log.info("\tAdding Organism %s", org_cn)
        data = wa.organisms.addOrganism(
            org_cn,
            args.jbrowse,
            genus=args.genus,
            species=args.species,
            public=args.public,
            # assign the gx_user as the organism creator
            metadata={'creator': gx_user.userId}
        )

        # Must sleep before we're ready to handle
        time.sleep(2)
        log.info("\tUpdating organism %s permissions for user %s", org_cn, gx_user)
        # assign the gx_user organism administrative privilege
        wa.users.updateOrganismPermission(
            gx_user, org_cn,
            administrate=True,
            write=True,
            export=True,
            read=True,
        )

    # Group access
    groups = json.loads(args.group)
    for group in groups:
        if group["group"] != "None":
            log.info("\tUpdating organism %s permission for group %s", org_cn, group["group"])
            res = wa.groups.updateOrganismPermission(group["group"], org_cn,
                                                     administrate=checkPermission("admin"),
                                                     write=checkPermission("write"),
                                                     read=checkPermission("read"),
                                                     export=checkPermission("export"))

    try:
        data = [o for o in data if o['commonName'] == org_cn]
        print(json.dumps(data, indent=2))
    except Exception:
        print(data['error'])
