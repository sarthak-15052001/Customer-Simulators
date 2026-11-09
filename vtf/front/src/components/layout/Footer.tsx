import AddCircleIcon from "@mui/icons-material/AddCircle";
import RemoveCircleIcon from "@mui/icons-material/RemoveCircle";
import Collapse from "@mui/material/Collapse";
import { useState } from "react";

import imgANCV from "../../assets/ancv.png";
import imgCB from "../../assets/cb.png";
import imgCheque from "../../assets/cheque.png";
import imgMastercard from "../../assets/mastercard.png";
import imgVisa from "../../assets/visa.png";
import { useTranslation } from "../../contexts/LanguageContext";
import { Box, Link, Typography } from "../ui";
import { VtfCountryFlag } from "./HeaderIcons";
import { VTF_HEADER } from "./headerVtfStyles";
import {
  FOOTER_COL1_LINKS,
  FOOTER_COL2_LINKS,
  FOOTER_COL3_LINKS,
  FOOTER_LEGAL_LINKS,
} from "./footerLinks";
import { vtfUrl } from "../../config/site";
import {
  footerBottomInnerSx,
  footerBottomLinkSx,
  footerBottomSx,
  footerColumnSx,
  footerColumnsSx,
  footerColumnTitleSx,
  footerContactCtaSx,
  footerContactInnerSx,
  footerContactSx,
  footerContactTaglineSx,
  footerHoursSx,
  footerLinkSx,
  footerMainInnerSx,
  footerMainPatternSx,
  footerMainSx,
  footerPaymentsSx,
  footerPaymentsTitleSx,
  footerPhoneSx,
  footerSocialLinkSx,
} from "./footer.ui";

function VtfLogoFooter() {
  return (
    <Box sx={{ mb: 3, display: "flex", justifyContent: "center" }}>
      <svg
        aria-hidden="true"
        xmlns="http://www.w3.org/2000/svg"
        width="160"
        height="81"
        viewBox="0 0 160 81"
      >
        <g fill="none" fillRule="evenodd">
          <path
            fill="#FFF"
            d="M1.097 75.662H0v5.243h3.448v-.969h-2.35v-4.274zm8.464 0h-3.61v5.243h3.708v-.969H7.048v-1.328h1.846v-.912H7.048V76.63H9.56v-.968zm4.54-.096c-1.008 0-1.78.58-1.78 1.486 0 .738.536 1.167 1.3 1.51l.578.253c.423.191.683.31.683.652 0 .366-.292.58-.765.58-.643 0-1.024-.365-1.317-.762l-.756.556c.398.698 1.146 1.159 2.073 1.159 1.066 0 1.879-.595 1.879-1.573 0-.746-.48-1.167-1.325-1.534l-.61-.262c-.39-.175-.627-.301-.627-.604 0-.35.31-.509.667-.509.44 0 .765.223 1.026.604l.747-.563c-.317-.572-.918-.993-1.773-.993zm11.964.096l-1.334 3.177-1.342-3.177h-1.244L24.544 81h.366l2.39-5.338h-1.235zm6.624 5.243h1.179l-2.39-5.339h-.367l-2.399 5.339h1.18l.3-.684h2.196l.3.684zm-.683-1.564h-1.432l.716-1.772.716 1.772zm6.626-3.775c-1.603 0-2.862 1.175-2.862 2.717S37.03 81 38.624 81c1.041 0 1.911-.5 2.374-1.302l-.829-.572c-.358.556-.862.882-1.537.882-1 0-1.732-.707-1.732-1.717 0-1.017.732-1.732 1.732-1.732.675 0 1.18.326 1.537.882l.83-.573c-.472-.802-1.334-1.302-2.367-1.302zm8.419 5.339h1.18l-2.392-5.339h-.365l-2.399 5.339h1.179l.301-.684h2.195l.301.684zm-.683-1.564h-1.43l.714-1.772.716 1.772zm7.802-3.68v3.13l-3.116-3.225h-.357v5.339h1.097v-3.146L54.901 81h.366v-5.338H54.17zm6.698-.095c-1.602 0-2.862 1.175-2.862 2.717S59.266 81 60.86 81c1.041 0 1.912-.5 2.375-1.302l-.83-.572c-.357.556-.862.882-1.537.882-1 0-1.732-.707-1.732-1.717 0-1.017.731-1.732 1.732-1.732.675 0 1.18.326 1.538.882l.83-.573c-.473-.802-1.335-1.302-2.368-1.302zm8.653.096h-3.61v5.243h3.707v-.969h-2.61v-1.328h1.845v-.912h-1.845V76.63h2.513v-.968zm4.54-.096c-1.009 0-1.78.58-1.78 1.486 0 .738.536 1.167 1.3 1.51l.578.253c.423.191.683.31.683.652 0 .366-.292.58-.765.58-.643 0-1.025-.365-1.318-.762l-.755.556c.398.698 1.146 1.159 2.073 1.159 1.066 0 1.878-.595 1.878-1.573 0-.746-.48-1.167-1.324-1.534l-.61-.262c-.392-.175-.627-.301-.627-.604 0-.35.309-.509.667-.509.44 0 .765.223 1.025.604l.748-.563c-.317-.572-.918-.993-1.773-.993zm12.59.096h-4.538v.968h1.716v4.275h1.097V76.63h1.724v-.968zm6.991 5.243l-1.52-2.058c.577-.278.942-.817.942-1.494 0-1.024-.804-1.691-1.934-1.691h-2.017v5.243h1.097v-1.852h.805l1.391 1.852h1.236zm-3.432-4.3h.92c.512 0 .813.311.813.748 0 .454-.3.756-.813.756h-.92v-1.503zm7.464-2.93h-1.326v.19l1.114 1.287h.797l-.585-1.476zm2.016 1.987h-3.61v5.243h3.708v-.969h-2.61v-1.328h1.846v-.912h-1.847V76.63h2.513v-.968zm4.54-.096c-1.008 0-1.78.58-1.78 1.486 0 .738.536 1.167 1.3 1.51l.578.253c.423.191.684.31.684.652 0 .366-.293.58-.765.58-.643 0-1.025-.365-1.317-.762l-.756.556c.398.698 1.146 1.159 2.073 1.159 1.065 0 1.878-.595 1.878-1.573 0-.746-.479-1.167-1.325-1.534l-.61-.262c-.39-.175-.627-.301-.627-.604 0-.35.31-.509.668-.509.439 0 .765.223 1.025.604l.747-.563c-.317-.572-.918-.993-1.772-.993zm12.086.096h-3.53v5.243h1.098V78.91h1.993v-.968h-1.993V76.63h2.432v-.968zm5.633 5.243h1.178l-2.39-5.339h-.366l-2.398 5.339h1.179l.3-.684h2.196l.3.684zm-.684-1.564h-1.43l.715-1.772.715 1.772zm9.225-3.775l-2.27 2.836-2.268-2.836h-.357v5.339h1.097v-2.797l1.35 1.653h.358l1.35-1.653v2.797h1.098v-5.339h-.358zm3.422 5.339h1.097v-5.243h-1.097v5.243zm5.238-5.243h-1.097v5.243h3.448v-.969h-2.35v-4.274zm5.95 0h-1.096v5.243h3.447v-.969h-2.35v-4.274zm8.465 0h-3.61v5.243h3.707v-.969h-2.61v-1.328h1.846v-.912h-1.846V76.63h2.513v-.968zm4.54-.096c-1.008 0-1.78.58-1.78 1.486 0 .738.536 1.167 1.3 1.51l.578.253c.423.191.684.31.684.652 0 .366-.294.58-.766.58-.642 0-1.024-.365-1.317-.762l-.756.556c.398.698 1.146 1.159 2.073 1.159 1.066 0 1.879-.595 1.879-1.573 0-.746-.48-1.167-1.325-1.534l-.61-.262c-.391-.175-.627-.301-.627-.604 0-.35.31-.509.667-.509.44 0 .765.223 1.025.604l.748-.563c-.317-.572-.919-.993-1.773-.993z"
          />
          <path
            fill="#F4A27E"
            d="M22.315 27.94a4.63 4.63 0 014.268 2.825l.049.12 10.447 26.832 10.509-26.84a4.63 4.63 0 014.184-2.935l.13-.001h6.322v5.876h-5.067l.007.01L41.09 63.51a4.194 4.194 0 01-3.76 2.608l-.128.002h-.154a4.196 4.196 0 01-3.846-2.512l-.049-.115-11.912-29.667.007-.01H16V27.94h6.315zm14.137-16.767c2.64 0 4.78 2.133 4.78 4.763 0 2.631-2.14 4.764-4.78 4.764a4.774 4.774 0 01-4.78-4.639l-.001-.125v-4.763h4.78z"
          />
          <path
            fill="#FFF"
            d="M72.915 25.157a19.677 19.677 0 0117.562-.127l.227.113 4.222 2.136a6.139 6.139 0 002.583.66l.193.003h4.957v5.874h-4.957c-.9 0-1.79-.198-2.603-.578l-.173-.084-4.222-2.137a19.615 19.615 0 00-5.652-1.843l-.324-.051v36.924h-5.845V29.128a19.665 19.665 0 00-5.668 1.754l-.3.15-4.17 2.117a6.145 6.145 0 01-2.591.664l-.193.003h-4.956v-5.874h4.956c.903 0 1.794-.2 2.61-.582l.174-.085 4.17-2.118zM81.805 0l3.381 3.368a4.75 4.75 0 010 6.736 4.793 4.793 0 01-6.761 0 4.752 4.752 0 01-.097-6.637l.097-.099L81.805 0z"
          />
          <path
            fill="#B4DAC3"
            d="M147.505 27.942v5.874h-26.541v8.833h10.825v5.863h-10.825l4.03 17.535h-5.903l-3.248-14.128a30.819 30.819 0 01-.78-6.467l-.003-.435V33.816h-9.593v-5.874h42.038zM131.94 11.173v4.763c0 2.631-2.14 4.764-4.78 4.764-2.641 0-4.781-2.133-4.781-4.764 0-2.589 2.072-4.695 4.655-4.761l.125-.002h4.78z"
          />
        </g>
      </svg>
    </Box>
  );
}

function FooterAccordionColumn({
  title,
  children,
  defaultOpen = true,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Box sx={footerColumnSx}>
      <Box
        component="button"
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          width: "100%",
          p: 0,
          border: 0,
          bgcolor: "transparent",
          color: "inherit",
          cursor: { xs: "pointer", lg: "default" },
          pointerEvents: { lg: "none" },
          mb: { xs: open ? 1.5 : 0, lg: 2.5 },
          textAlign: "left",
        }}
      >
        <Typography component="span" sx={footerColumnTitleSx}>
          {title}
        </Typography>
        <Box
          component="span"
          aria-hidden
          sx={{ display: { xs: "flex", lg: "none" }, color: "#fff" }}
        >
          {open ? (
            <RemoveCircleIcon fontSize="small" />
          ) : (
            <AddCircleIcon fontSize="small" />
          )}
        </Box>
      </Box>

      <Collapse in={open} sx={{ display: { xs: "block", lg: "none" } }}>
        {children}
      </Collapse>
      <Box sx={{ display: { xs: "none", lg: "block" } }}>{children}</Box>
    </Box>
  );
}

const SOCIALS = [
  {
    href: "https://www.facebook.com/vtfvacances",
    label: "Facebook",
    icon: (
      <svg width="19" height="19" viewBox="0 0 19 19" aria-hidden="true">
        <path
          fill="#FFF"
          fillRule="evenodd"
          d="M9.368.25C4.296.25.184 4.417.184 9.556c0 4.647 3.362 8.499 7.755 9.194v-6.505H5.592V9.556h2.347l.002-2.05c0-2.332 1.363-3.626 3.46-3.626 1.006 0 2.049.195 2.049.195V6.35H12.3c-1.142 0-1.506.725-1.506 1.46l.003 1.746h2.55l-.407 2.689h-2.143v6.505c4.393-.695 7.754-4.547 7.754-9.194 0-5.14-4.111-9.306-9.183-9.306z"
        />
      </svg>
    ),
  },

  {
    href: "https://www.instagram.com/vtfvacances/",
    label: "Instagram",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 19" aria-hidden="true">
        <path
          fill="#FFF"
          fillRule="evenodd"
          d="M9.207.25h1.83l1.493.01.596.013.783.032c.977.045 1.645.202 2.23.43a4.497 4.497 0 011.625 1.067c.512.515.825 1.03 1.06 1.639.227.588.382 1.26.427 2.245l.033.82.017.935.005 1.57-.003 2.236-.02 1.247-.023.625a190.6 190.6 0 01-.01.195c-.044.985-.199 1.657-.426 2.246a4.535 4.535 0 01-1.06 1.638 4.5 4.5 0 01-1.626 1.068c-.584.228-1.252.384-2.229.43l-.633.026-.596.016-1.023.01-.62.002-2.628-.003-1.169-.016-.742-.028-.163-.008c-.978-.045-1.645-.2-2.229-.43a4.5 4.5 0 01-1.626-1.067 4.535 4.535 0 01-1.06-1.638c-.227-.589-.382-1.261-.427-2.246l-.031-.788-.014-.6-.009-1.504.004-2.889.012-.834.018-.548.02-.465c.045-.985.2-1.657.427-2.245A4.538 4.538 0 012.48 1.8 4.497 4.497 0 014.106.736C4.69.507 5.357.35 6.335.305l.84-.034.721-.014L9.207.25zm3.465 1.679l-.514-.007H8.086l-.731.012-.622.022-.322.014c-.758.035-1.222.148-1.544.259l-.162.06a2.845 2.845 0 00-1.055.691c-.322.324-.52.632-.687 1.065l-.06.162-.03.092-.058.208a5.85 5.85 0 00-.158 1.054l-.035.765-.016.546-.012 1.484.004 3.153.01.732.024.683.014.314c.025.555.092.954.169 1.255l.059.208.03.092.059.163c.166.432.365.74.687 1.064.32.323.627.524 1.055.692l.162.06c.292.1.703.203 1.344.247l.994.043.915.017 1.307.005 2.697-.005.915-.017.794-.032a6.046 6.046 0 001.246-.17l.206-.059.176-.06.078-.03a2.835 2.835 0 001.055-.691c.322-.324.52-.632.687-1.064l.06-.163.06-.192c.088-.312.168-.739.197-1.363l.032-.796.015-.791.006-1.245-.002-2.474-.017-1.287-.034-.883c-.032-.694-.128-1.144-.227-1.463l-.06-.176a2.863 2.863 0 00-.716-1.142 2.845 2.845 0 00-1.056-.693l-.162-.06a3.86 3.86 0 00-.092-.03l-.206-.059a5.707 5.707 0 00-1.046-.158l-.522-.025-.839-.027zm-2.55 2.82c2.605 0 4.716 2.128 4.716 4.751s-2.111 4.75-4.716 4.75-4.716-2.127-4.716-4.75 2.111-4.75 4.716-4.75zm0 1.668c-1.69 0-3.06 1.38-3.06 3.083 0 1.703 1.37 3.084 3.06 3.084s3.062-1.381 3.062-3.084-1.371-3.083-3.062-3.083zm4.903-2.965c.608 0 1.102.497 1.102 1.11 0 .613-.494 1.11-1.102 1.11a1.106 1.106 0 01-1.103-1.11c0-.613.494-1.11 1.103-1.11z"
        />
      </svg>
    ),
  },

  {
    href: "https://www.linkedin.com/company/10631010/",
    label: "LinkedIn",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" aria-hidden="true">
        <path
          fill="#FFF"
          fillRule="evenodd"
          d="M15 15h-3.082V9.75c0-1.44-.547-2.243-1.686-2.243-1.24 0-1.887.837-1.887 2.244V15h-2.97V5h2.97v1.347s.894-1.652 3.015-1.652S15 5.99 15 8.668V15zM1.831 3.69A1.839 1.839 0 010 1.846C0 .826.82 0 1.831 0c1.012 0 1.832.826 1.832 1.845a1.84 1.84 0 01-1.832 1.846zM.298 15h3.096V5H.298v10z"
        />
      </svg>
    ),
  },
];

/** VTF shop and partner sites open in a new tab (same as header). */
function footerHrefProps(href: string) {
  if (href.startsWith("tel:")) return {};
  return { target: "_blank" as const, rel: "noopener noreferrer" };
}

export function Footer() {
  const { t, language } = useTranslation();

  return (
    <Box component="footer" id="app-footer" sx={{ mt: "auto" }}>
      <Box sx={footerMainSx}>
        <Box aria-hidden sx={footerMainPatternSx} />
        <Box sx={footerMainInnerSx}>
          <Box sx={footerColumnsSx}>
            <FooterAccordionColumn title={t("footer.col1.title")}>
              {FOOTER_COL1_LINKS.map(({ key, href }) => (
                <Link
                  key={key}
                  href={key === "agencies" ? vtfUrl(t("footer.contact.contactUrl"), language) : href}
                  {...footerHrefProps(href)}
                  sx={footerLinkSx}
                >
                  {t(`footer.col1.${key}`)}
                </Link>
              ))}
              <Typography sx={footerPaymentsTitleSx}>
                {t("footer.payments.title")}
              </Typography>
              <Box sx={footerPaymentsSx}>
                <img src={imgMastercard} alt="Mastercard" />
                <img src={imgCB} alt="CB" />
                <img src={imgVisa} alt="Visa" />
                <img src={imgCheque} alt="Chèques Vacances" />
                <img src={imgANCV} alt="ANCV" />
              </Box>
            </FooterAccordionColumn>

            <FooterAccordionColumn title={t("footer.col2.title")}>
              {FOOTER_COL2_LINKS.map(({ key, href }) => (
                <Link
                  key={key}
                  href={href}
                  {...footerHrefProps(href)}
                  sx={footerLinkSx}
                >
                  {t(`footer.col2.${key}`)}
                </Link>
              ))}
            </FooterAccordionColumn>

            <FooterAccordionColumn title={t("footer.col3.title")}>
              {FOOTER_COL3_LINKS.map(({ key, href }) => (
                <Link
                  key={key}
                  href={href}
                  {...footerHrefProps(href)}
                  sx={footerLinkSx}
                >
                  {t(`footer.col3.${key}`)}
                </Link>
              ))}
            </FooterAccordionColumn>


          </Box>

          <Box sx={footerContactSx}>
            <Box sx={footerContactInnerSx}>
              <VtfLogoFooter />
              <Typography sx={footerContactTaglineSx}>
                {t("footer.contact.tagline")}
              </Typography>

              <Box
                sx={{
                  display: "flex",
                  justifyContent: "center",
                  gap: 1.25,
                  mb: 3,
                }}
              >
                {SOCIALS.map((social) => (
                  <Box
                    key={social.label}
                    component="a"
                    href={social.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={social.label}
                    sx={footerSocialLinkSx}
                  >
                    {social.icon}
                  </Box>
                ))}
              </Box>

              <Link href="tel:0442123200" sx={footerPhoneSx}>
                <VtfCountryFlag
                  src={VTF_HEADER.flags.france}
                  alt="France"
                  size={16}
                />
                {t("footer.contact.frPhone")}
              </Link>
              <Typography sx={footerHoursSx}>
                {t("footer.contact.frHours1")} {t("footer.contact.frHours2")}
              </Typography>

              <Link href="tel:+3225461410" sx={footerPhoneSx}>
                <VtfCountryFlag
                  src={VTF_HEADER.flags.belgique}
                  alt="Belgique"
                  size={16}
                />
                {t("footer.contact.bePhone")}
              </Link>
              <Typography sx={footerHoursSx}>
                {t("footer.contact.beHours1")} {t("footer.contact.beHours2")}
              </Typography>

              <Link
                href={vtfUrl(t("footer.contact.contactUrl"), language)}
                {...footerHrefProps(vtfUrl(t("footer.contact.contactUrl"), language))}
                sx={footerContactCtaSx}
              >
                {t("footer.contact.cta")}
              </Link>
            </Box>
          </Box>
        </Box>
      </Box>

      <Box sx={footerBottomSx}>
        <Box sx={footerBottomInnerSx}>
          <Typography sx={{ fontSize: "inherit" }}>{t("footer.rights")}</Typography>
          <Box
            component="ul"
            sx={{
              display: "flex",
              flexWrap: "wrap",
              justifyContent: "center",
              gap: 0,
              m: 0,
              p: 0,
              listStyle: "none",
            }}
          >
            {FOOTER_LEGAL_LINKS.map(({ key, href }) => (
              <Box
                component="li"
                key={key}
                sx={{
                  fontSize: "inherit",
                  "& + li::before": {
                    content: '"·"',
                    mx: 0.75,
                  },
                }}
              >
                <Link
                  href={href}
                  {...footerHrefProps(href)}
                  sx={footerBottomLinkSx}
                >
                  {t(`footer.links.${key}`)}
                </Link>
              </Box>
            ))}
          </Box>
          <Typography sx={{ fontSize: "inherit" }}>
            {t("footer.links.conception")}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
