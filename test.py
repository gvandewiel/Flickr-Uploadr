import pkg_resources
import re

regex = r"(^[a-zA-Z]*)"
dist = 'FlickrUploadr'

# Get a reference to an EntryPoint, somehow.
pe = pkg_resources.get_entry_map(dist)

failed = []

for group in pe:
    for name in iter(pe[group]):
        print('\n{}, {}, {}'.format(dist, group, name))
        plug = pkg_resources.get_entry_info(dist, group, name)

        # This is sub-optimal because it raises on the first failure.
        # Can't capture a full list of failed dependencies.
        # plug.require()
        # Instead, we find the individual dependencies.
        
        for extra in sorted(plug.extras):
            if extra not in plug.dist._dep_map:
                continue  # Not actually a valid extras_require dependency?
            
            for requirement in plug.dist._dep_map[extra]:
                try:
                    pkg_resources.require(str(requirement))
                except pkg_resources.VersionConflict:
		    mod = re.match(regex, str(requirement)).group()
                    req_ver = str(requirement).replace(mod,'')
		    cur_ver = pkg_resources.get_distribution(str(mod)).version
                    print('\t"{}" module found, but with different version ({}) than required ({})'.format(mod, cur_ver, req_ver))
                    failed.append(plug.name)
                except pkg_resources.DistributionNotFound:
		    print('\t{} can not be found'.format(requirement))
                    failed.append(plug.name)
        
failed = list(set(failed))
print(failed)
