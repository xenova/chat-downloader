Chat Item Fields
================

First of all, each chat item is a dictionary. The following tables
list and provide explanations for the various fields that a chat
item may possess.


If you find a field that is not listed below,
please notify the developers by creating an issue, or adding
the relevant documentation in a pull request.


.. note::
   It is recommended to treat every field listed below as optional.
   While most items contain basic information such as `timestamp`,
   `message` or `author`, it cannot be guaranteed that every item
   will contain these fields.


.. list-table:: Common fields
   :widths: 20 10 70
   :header-rows: 1

   * - Field
     - Type
     - Description
   * - timestamp
     - float
     - UNIX time (in microseconds) of when the message was sent.
   * - message
     - string
     - Actual content/text of the chat item.
   * - message_id
     - string
     - Identifier for the chat item.
   * - message_type
     - string
     - Message type of the item.
   * - author
     - dictionary
     - A dictionary containing information about the user who sent the message. For author fields, see :ref:`here <Author fields table>`.
   * - time_in_seconds
     - float
     - The number of seconds after the video began, that the message was sent.  This is only present for replays/vods/clips (i.e. a video which is not live).
   * - time_text
     - string
     - Human-readable format for `time_in_seconds`.

Documentation for other (less common) fields can be found :ref:`here <Other fields table>`.

.. _Author fields table:

.. list-table:: Author fields
   :widths: 20 10 70
   :header-rows: 1

   * - Field
     - Type
     - Description
   * - name
     - string
     - The name of the author.
   * - id
     - string
     - Idenfifier for the author.
   * - display_name
     - string
     - The name of the author which is displayed to the viewer. This may be different to `name`.
   * - short_name
     - string
     - A shortened version of the author's name.
   * - type
     - string
     - Type of the author.
   * - url
     - string
     - URL of the author's channel/page.
   * - images
     - list
     - A list which contains different sizes of the author's profile picture. See :ref:`here <Image fields table>` for the fields that an image may have.
   * - badges
     - list
     - A list of the author's badges. See :ref:`here <Badge fields table>` for the fields that a badge may have.
   * - gender
     - string
     - Gender of the author.
   * - is_banned
     - boolean
     - `True` if the user is banned, `False` otherwise.
   * - is_bot
     - boolean
     - `True` if the user is a bot, `False` otherwise.
   * - is_non_coworker
     - boolean
     - `True` if the user is not a coworker, `False` otherwise.
   * - is_original_poster
     - boolean
     - `True` if the user is the original poster, `False` otherwise.
   * - is_verified
     - boolean
     - `True` if the user is verified, `False` otherwise.

.. _Image fields table:

.. list-table:: Image fields
   :widths: 20 10 70
   :header-rows: 1

   * - Field
     - Type
     - Description
   * - url
     - string
     - The URL of the actual image
   * - width
     - integer
     - The width of the image
   * - height
     - integer
     - The height of the image
   * - image_id
     - string
     - A identifier for the image, usually of the form: {width}x{height}

.. _Badge fields table:

.. list-table:: Badge fields
   :widths: 20 10 70
   :header-rows: 1

   * - Field
     - Type
     - Description
   * - title
     - string
     - The title of the badge.
   * - id
     - string
     - Identifier for the badge.
   * - name
     - string
     - Name of the badge.
   * - version
     - integer
     - Version of the badge.
   * - icon_name
     - string
     - Name of the badge icon.
   * - icons
     - list
     - A list of images for the badge icons. See :ref:`here <Image fields table>` for potential fields.
   * - description
     - string
     - The description of the badge.
   * - alternative_title
     - string
     - Alternative title of the badge.
   * - click_action
     - string
     - Action to perform if the badge is clicked.
   * - click_url
     - string
     - URL to visit if the badge is clicked.

.. _Other fields table:

.. list-table:: Other fields
   :widths: 20 10 70
   :header-rows: 1

   * - Field
     - Type
     - Description
   * - amount
     - float
     - The amount of money that was sent with the message.
   * - sub_message
     - string
     - Additional text of the message.
   * - action_type
     - string
     - Action type of the item.
   * - tooltip
     - string
     - Text to be displayed when hovering over the message.
   * - icon
     - string
     - Icon associated with the message.
   * - target_message_id
     - string
     - The identifier for a message which this message references.
   * - action
     - string
     - The action of the message.
   * - viewer_is_creator
     - boolean
     - Whether the viewer is the creator or not.
   * - sticker_images
     - list
     - A list which contains different sizes of the sticker image. See :ref:`here <Image fields table>` for image fields.
   * - sponsor_icons
     - list
     - A list which contains different sizes of the sponsor image. See :ref:`here <Image fields table>` for image fields.
   * - ticker_icons
     - list
     - A list which contains different sizes of the ticker image. See :ref:`here <Image fields table>` for image fields.
   * - ticker_duration
     - float
     - How long the ticker message is displayed for.
   * - field
     - type
     - description
   * - field
     - type
     - description
   * - field
     - type
     - description
   * - field
     - type
     - description
   * - field
     - type
     - description
   * - field
     - type
     - description


The following fields indicate HEX colour information for the message:

author_name_text_colour
timestamp_colour
body_background_colour
header_text_colour
header_background_colour
body_text_colour
background_colour
money_chip_text_colour
money_chip_background_colour
start_background_colour
amount_text_colour
end_background_colour
detail_text_colour
