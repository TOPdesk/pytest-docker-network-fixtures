# Docker image management

On the surface this might not be a subject that warrants much attention: the Docker 
image name seems to contain all that you need to know about it: the registry (if 
present), the base name of the image, and the tag (if present). In practice, however, 
things are a bit more subtle.

## Image types

### Public images

This is the most straightforward case: we need to make sure our local Docker image 
matches the one in that public registry, and the only way of ensuring this is to do a 
_pull_ at the beginning of each test session. Failing to do that could mean the local 
Docker image is outdated, leading to all kinds of problems, like test runs leading to 
different results on different machines, including the CI.

### Images on private, 3rd party registries

For third-party registries, that host images that you want to _pull_, but don't want 
to _push_ images to, the situation is much like the one above. The main difference is 
that you'll probably be required to do a `docker login` before being able to pull from 
that registry.

### Local images

If the image is local only, that, too, would be straightforward: just don't try to 
pull that image. These would typically be images that you yourself create in your 
build process, just before running the tests. Note while this is pretty trivial on a 
developer's machine, on a CI you might be forced to jump through a few hoops to get 
this to work consistently.

### Images on your registry

What we mean by 'your registry' is a Docker registry that you or your organization 
uses to store the Docker images on that are built as part of your development process. 
This where things get tricky: does `my-registry/funky-image:snaphot` refer to 
an image we just built and available locally, or an image that's stored on `my-registry` 
and we need to pull before using it? Keep in mind: pushing local images before the 
tests have run successfully is not a great idea, and even then the image tag is 
likely to be changed before the eventual push, e.g. to a real version number, instead 
of `snapshot`.

And there may be some weird corner cases. One example would be where you're working on 
two projects at the same time, and you use the images produced in the one project in 
the tests of the other. You might not need to do that all that often, but having that 
workflow be available as an option can definitely be a nice time saver.

